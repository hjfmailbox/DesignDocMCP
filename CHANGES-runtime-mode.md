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

## 给后续 Agent 的注意事项
- 要把某个客户端从 STEP 升级为 LOOP：先用能力压测验证（单次阻塞 + 连续多轮 + 无需确认），再把其 `client_type` 加入 `KNOWN_PERSISTENT_CLIENTS`。不要凭感觉加。
- 调整轮询节奏改 `WAIT_FOR_TASK_TIMEOUT`，但不要超过最低客户端单次调用硬上限（当前 300s）。
- 若有从 `skills/` 同步到各 IDE 专属目录（`.cursor/skills/`、`.claude/skills/` 等）的机制，新增的 `skills/resume/` 需一并纳入同步。
- 客户端注册时应传 `client_type`（`cursor`/`claude_code`/`kimi`/`atomcode`/`generic`），否则默认按未知→STEP 处理。
