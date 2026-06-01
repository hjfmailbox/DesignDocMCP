# 变更记录：运行时模式检测与双模参与（LOOP / STEP）

> 目的：不同 Agent 客户端（Claude Code / Cursor / Kimi / AtomCode / Trae 等）维持"长时间运行不断开"的能力差异很大，有的甚至不支持。本次改动让系统**自动检测**客户端能力，并按能力分两种模式参与协作，避免在不支持的客户端上"静默假装循环"。

## 背景结论（压力测试得出）

对四家客户端做过单次阻塞 + 连续 40 轮调用压测，结论：

| 客户端 | 单次前台调用阻塞上限 | 连续调用/回合时长 | 需确认 |
|--------|----------------------|-------------------|--------|
| Claude Code | ≥420s | 无上限 | 否 |
| Cursor (CLI/Composer) | ≥420s | 无上限 | 否 |
| Kimi CLI | **硬上限 300s** | 无上限 | 否 |
| AtomCode | **硬上限 300s** | 无上限 | 否 |

- 四家都能跑自主循环（无次数/回合时长上限、无需确认）。
- 真正脆弱的是"单次调用阻塞上限"，Kimi/AtomCode 硬顶 300s。
- 关键决策：循环改用**短轮询**（`wait_for_task(timeout=25)`）而非单次长阻塞，从而统一规避 300s 硬顶与"Shell 超时 ≠ MCP 超时"的不确定性；实时性要求低，短轮询完全够用。
- 未在已知列表的客户端（含 Trae）**保守默认走 STEP 模式**，绝不假设其支持长循环。

## 两种运行时模式

| `runtime_mode` | 含义 | 参与方式 |
|----------------|------|----------|
| `persistent_worker`（LOOP） | 客户端能长时自主循环 | `wait_for_task(timeout=25)` → `submit_result` 短轮询循环，全程自主 |
| `normal_worker`（STEP） | 客户端无法长时保活 | 每次唤起只走一步（`heartbeat`→`get_phase_context`→提交对应阶段），随后停下，由用户 `/resume` 重新唤醒 |

检测在**服务端**完成，依据 `client_type`。LLM Agent 只有被唤起时才思考、MCP 无法 push 唤醒它，所以 STEP 模式靠 `/resume`（或客户端自带调度器，如 Cursor `/loop`）手动/定时泵。

## 具体改了哪些文件

### 1. `src/designdoc_mcp/constants.py`
- `WAIT_FOR_TASK_TIMEOUT`：`300` → **`25`**（短轮询默认值）。附注释：建议范围 20~60s，**务必 < 已知客户端单次调用硬上限 300s**，可手动调整。
- 新增 `KNOWN_PERSISTENT_CLIENTS = frozenset({"cursor", "claude_code", "atomcode", "kimi"})`（LOOP 能力白名单，集中维护）。
- 新增 `RUNTIME_MODE_LOOP = "persistent_worker"`、`RUNTIME_MODE_STEP = "normal_worker"`。

### 2. `src/designdoc_mcp/engine.py`
- 新增模块级函数 `detect_runtime_mode(client_type)`：命中白名单→LOOP，否则→STEP（含大小写/空格归一化）。
- `register_agent`：
  - 新注册路径：用 `detect_runtime_mode(client_type)` 替换原来"永远返回 persistent_worker"的空操作判断。
  - rejoin 路径：`a.runtime_mode` 改为按 `a.client_type` 重新判定（原来被强制写死 `persistent_worker`）。
- 从 `constants` 导入上述新符号。

### 3. `src/designdoc_mcp/server.py`
- `designdoc_guide` prompt 同步重写：Quick Start 按 `runtime_mode` 分流说明 LOOP/STEP，列出已知 LOOP 客户端与"其余→STEP"，新增 `/resume` 命令说明。
- 注意：`WAIT_FOR_TASK_TIMEOUT` 作为 `wait_for_task` 默认参数随常量自动变为 25。

### 4. `skills/register/SKILL.md`（重写）
- 双模协议：先读 `register_agent` 返回的 `runtime_mode` 再分支，严禁自行猜测模式。
- 含已知客户端能力表 + 如何传 `client_type` / `agent_identity`（稳定 identity 用于自动 rejoin）。
- LOOP 段：短轮询循环（`timeout=25`，注释标范围）。
- STEP 段：单步后停下并提示 `/resume`。
- 明令禁止：假装循环、单次长阻塞（如 timeout=300）、自我提升未验证客户端为 LOOP、写后台脚本"保活"、提交间向用户要确认。

### 5. `skills/resume/SKILL.md`（新增）
- STEP 模式手动泵：执行一步（heartbeat→get_phase_context→对应阶段 submit），随后停下并报告状态 + 下次唤醒时机。
- 仅用于 STEP 模式；LOOP 模式无需 `/resume`。

### 6. `skills/deregister/SKILL.md`
- 退出说明区分两种模式（LOOP 跳出循环 / STEP 不再 `/resume`）。

### 7. `src/designdoc_mcp/static/index.html`（Web UI，Alpine.js）
- Agents 卡片：`normal_worker` 显示 `STEP` 徽标。
- 当 STEP 模式 agent 活跃、会话进行中、且当前不是等待阶段（非 `clarify_review`/`human_review`，状态非 `created/completed/archived`）时，显示 `⏳ needs /resume` 提示用户唤醒时机。

### 8. `README.md`
- 命令表新增 `/resume`；新增"运行时模式与长时执行检测"小节（双模表 + 检测判据位置说明）。
- skill 目录表述更正为实际源目录 `skills/`（register/resume/deregister）。

### 9. `tests/test_engine.py`
- 新增 `TestRuntimeModeDetection`（11 例）：已知客户端→LOOP、未知/空/generic/trae→STEP、rejoin 时按新 client 重判。

## 验证
- `uv run pytest -q` → **137 passed**。

---

# 第二批：实测问题修复（同一主题的后续迭代）

实测后发现 4 个问题，根因与修复如下。

## 问题与根因

1. **Claude Code / Cursor 退化为 STEP（应为 LOOP）**：根因是检测**依赖 Agent 自报 `client_type`**，而 Cursor 实测传了 `client_type=''`（空）。日志佐证：`name='Cursor Composer Agent', identity='', client_type=''`。
2. **`/resume` 与 Cursor 内置命令冲突**。
3. **掉线 Agent 无法 rejoin**：Kimi 在 critic 掉线被注销，进入 revision 后用相同 identity 重注册被拒（`Cannot register new agents during revision phase`）。根因有二：(a) rejoin 仅在传了 `agent_identity` 时生效，Kimi 没传稳定 identity；(b) 即使 `agent_id` 已在名册，阶段限制检查也排在"按 agent_id 复用"之前，导致回归 Agent 被当作新 Agent 拦截。且 **Web UI 无任何人工干预按钮**可解锁。
4. 日志复盘（见下）。

## 关键发现：MCP 握手自带客户端身份

MCP `initialize` 握手携带 `clientInfo.name`，实测各客户端取值：`claude-code`、`Cursor`、`cursor-vscode`、`Trae`、以及通用的 `mcp`（Kimi 走此通用名，但其 Agent 名称含 "Kimi"）。因此**服务端可直接识别客户端，无需信任 Agent 自报**。FastMCP 3.3.1 通过 `ctx.session.client_params.clientInfo` 暴露。

## 第二批改了哪些文件

### `src/designdoc_mcp/constants.py`
- 新增 `CLIENT_TYPE_KEYWORDS`：关键字→canonical client_type 的有序映射（claude_code/atomcode/cursor/kimi/trae），用于从多来源归一化识别。

### `src/designdoc_mcp/engine.py`
- 新增 `canonicalize_client_type(*candidates)`：按优先级扫描（client_type → clientInfo 提示 → name）返回 canonical client_type。
- 新增 `CollaborationEngine._resolve_runtime_mode(client_type, force_mode)`：支持 `force_mode` 覆盖（loop/step）。
- `register_agent` 重写（修复 #1、#3a）：
  - 新增参数 `client_info_hint`、`force_mode`。
  - 用 `effective_client = canonicalize_client_type(client_type, client_info_hint, name)` 做检测，不再只看自报 client_type。
  - **重排逻辑**：先按 identity rejoin；否则算出 agent_id，若该 agent_id **已在名册（即使 inactive）则直接复用回归**（原地恢复、保留 perspective），**不受阶段限制**；只有"全新 agent_id"才施加 critic/revision 等阶段限制。错误信息也补充了"复用相同 identity/name 即可回归"的提示。

### `src/designdoc_mcp/server.py`
- `register_agent` MCP 工具：新增注入参数 `ctx: Context`（FastMCP 自动注入，已验证不出现在 input schema 中）与 `force_mode`；从 `ctx.session.client_params.clientInfo` 读取 `name/title` 作为 `client_info_hint` 传给 engine。docstring 与 `designdoc_guide` prompt 同步更新（检测来源、auto-rejoin 说明、命令前缀）。

### `src/designdoc_mcp/web.py`
- 新增 REST 端点 `POST /api/sessions/{id}/request-human-review`（修复 #3 的 UI 缺口），调用 `engine.request_human_review` 将卡死会话强制转入 HUMAN_REVIEW（之后注册解禁）。

### `src/designdoc_mcp/static/index.html`
- 会话控制栏新增 **Force Human Review** 按钮：在 debate 阶段（proposal/critic/revision/optimization/devils_advocate/consensus 且非 completed/archived/human_review）显示，用于掉线卡死时解锁。

### Skills 命令前缀（修复 #2）
- 三个 SKILL.md 的 frontmatter `name` 与内部引用统一加 `dd-` 前缀：`/dd-register`、`/dd-resume`、`/dd-deregister`（**目录名未改**，命令由 frontmatter `name` 决定）。`README.md`、`designdoc_guide` prompt 同步更新。
- ⚠️ 若已同步 skill 到 IDE 专属目录（`.cursor/skills/` 等），需重新同步以让新命令名生效。

### `tests/test_engine.py`
- `TestRuntimeModeDetection` 增补：从 clientInfo 提示识别、从 name 识别（握手为通用 mcp 时）、`force_mode` 覆盖。
- 新增 `TestRejoinDuringRestrictedPhase`：revision 阶段下 按 agent_id / 按 identity 均可 rejoin；全新 agent 仍被拦截。

## 验证
- `uv run pytest -q` → **152 passed**；lint clean。
- 已验证 `register_agent` 工具 schema 隐藏 `ctx`、暴露 `force_mode`。

## 第四项：本轮辩论日志复盘（session 8c68e2df8663）

时间线（`logs/designdoc_mcp.log`）：
- 17:45 cursor、kimi 注册；17:47 claude_code 注册（3 agent）。
- 17:55 进入 critic（push `submit_challenge` ×3）。
- 18:00–18:01 cursor、claude 提交 decision_points（critic 内）。kimi 未提交。
- 18:10:21 **kimi 被注销**（critic 期间掉线），phase 推进到 revision（剩 2 agent）。
- 18:10:28 / 18:11:07 / 18:13:13 kimi 反复重注册→被拒（revision 阶段）。← 本次 #3 修复点。
- 18:11:20 cursor 因带稳定 identity（`cursor_cli_designDocMCPTest1`）成功 auto-rejoin。
- 18:25:52 cursor 再次掉线，推进到 optimization。

结论：cursor 因传了稳定 identity 能自动回归，kimi 因未传稳定 identity 且命中阶段限制排序 bug 而被拒——印证了修复方向。另注意日志为 DEBUG 级、含大量 SSE 噪声（文件已 95MB），建议生产降到 INFO 或加轮转。

---

## 给后续 Agent 的注意事项
- 要把某个客户端从 STEP 升级为 LOOP：先用能力压测验证（单次阻塞 + 连续多轮 + 无需确认），再把其 `client_type` 加入 `KNOWN_PERSISTENT_CLIENTS`。不要凭感觉加。
- 调整轮询节奏改 `WAIT_FOR_TASK_TIMEOUT`，但不要超过最低客户端单次调用硬上限（当前 300s）。
- 若有从 `skills/` 同步到各 IDE 专属目录（`.cursor/skills/`、`.claude/skills/` 等）的机制，新增的 `skills/resume/` 需一并纳入同步。
- 客户端注册时**可**传 `client_type`，但已不强制——服务端会从 MCP `clientInfo.name` + name 自动识别。新增客户端识别词在 `constants.py::CLIENT_TYPE_KEYWORDS`，新增 LOOP 能力客户端在 `KNOWN_PERSISTENT_CLIENTS`。
- 需要手动指定模式时用 `register_agent(force_mode="loop"|"step")`。
- 掉线重连务必复用相同 `agent_identity` 与 name；否则会生成新 agent_id（虽然现在按 agent_id 也能复用，但 name 变了 agent_id 就变）。
- 建议将生产日志级别从 DEBUG 降到 INFO 并加文件轮转（当前 `logs/designdoc_mcp.log` 已达 95MB，SSE DEBUG 噪声为主）。
