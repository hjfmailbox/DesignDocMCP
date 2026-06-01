# DesignDoc MCP

MCP驱动的多智能体设计文档协作系统。通过结构化辩论流程，让多个AI智能体围绕设计需求进行深度讨论，最终输出高质量的结构化设计文档。

## 核心理念

- **UI是控制中心**：人类在Web UI中创建会话、提交需求、观察流程、做出决策
- **Skill极简**：Agent只需安装skill，使用 `/dd-register` 加入，`/dd-deregister` 退出
- **自动参与**：Agent注册后自动心跳、自动检测阶段、自动提交内容
- **人类只做决策**：阶段自动推进，人类仅在决策点介入（通过UI操作）
- **结构化辩论**：4阶段澄清 + 6阶段辩论，强制深度思考

## 完整流程

```
┌─ 人类（Web UI）───────────────────────────────────────────────┐
│ 1. 打开 http://localhost:8765                                   │
│ 2. 点击 + 创建会话，填写标题和需求                              │
│ 3. 观察Agent注册、讨论流程、阶段进度                            │
│ 4. 在Decisions页面做出决策（假设审核/需求批准/辩论审核）         │
│ 5. 查看生成的设计文档                                          │
│ 6. 归档会话                                                    │
└────────────────────────────────────────────────────────────────┘

┌─ Agent（Skill）───────────────────────────────────────────────┐
│ 1. /dd-register  → 自动加入会话（无需参数）                       │
│ 2. 每次被唤起时：heartbeat → get_phase_context → 提交内容     │
│ 3. /dd-deregister → 退出会话                                      │
└────────────────────────────────────────────────────────────────┘
```

### 详细流程

```
人类: [UI] 创建会话 + 提交需求
      ↓
系统: 自动评估需求清晰度 (0.0~1.0)
      ↓
      ├─ 清晰度 ≥ 0.7 → 自动跳过澄清，直接进入辩论
      └─ 清晰度 < 0.7 → 进入4阶段澄清
           ↓
Agent A: /dd-register <session_id>
Agent B: /dd-register <session_id>
      ↓
┌─── 澄清阶段（如果需要）──────────────────────────────────────┐
│ Agent: submit_assumptions (各Agent独立提交假设，全部完成后推进) │
│ Agent: supplement_assumption_options (补充备选项，全部完成后推进)│
│ 人类: [UI] review_assumptions ← 决策点1（审核分歧假设）        │
│ Agent: submit_refined_requirement (重写需求，全部完成后)        │
│ 人类: [UI] approve_refined_requirement ← 决策点2（批准需求）   │
└──────────────────────────────────────────────────────────────┘
      ↓ 自动进入辩论
┌─── 辩论阶段（6阶段/轮，可多轮）─────────────────────────────┐
│ Agent自动: submit_proposal (从随机视角提出方案)               │
│ Agent自动: submit_challenge (挑战其他方案，禁止礼貌性同意)    │
│ Agent自动: submit_revision (根据反馈修订方案)                 │
│ Agent自动: submit_optimization (提出优化建议)                 │
│ Agent自动: submit_devils_advocate (魔鬼代言人分析)            │
│ Agent自动: cast_consensus_vote (共识投票)                     │
│                                                              │
│ 全票通过 → COMPLETED                                         │
│ 分歧 → 人类: [UI] approve/reject/override ← 决策点3          │
└──────────────────────────────────────────────────────────────┘
      ↓
人类: [UI] 查看设计文档 → 归档会话
```

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 启动MCP服务器

```powershell
# Windows（推荐）
.\start.ps1

# 或直接命令
uv run designdoc-mcp --transport http --port 8765

# 带日志
.\start.ps1 -LogDir "D:\logs\designdoc"

# 带API Token
.\start.ps1 -ApiToken "your-secret-token"
```

服务器启动后：
- **Web UI**: http://localhost:8765
- **MCP端点**: http://localhost:8765/mcp

### 3. 配置Agent连接

**任何支持MCP协议的Agent都可以连接**，不限于特定IDE或工具。只需配置MCP服务器连接即可：

```json
{
  "mcpServers": {
    "designdoc": {
      "type": "http",
      "url": "http://localhost:8765/mcp"
    }
  }
}
```

#### MCP配置文件位置

| Agent | 配置文件路径 | 说明 |
|-------|-------------|------|
| **Claude Code** | `.mcp.json` | 项目根目录，Claude Code 自动识别 |
| **Cursor** | `.cursor/mcp.json` | Cursor 自动识别项目级配置 |
| **Trae** | `.trae/mcp.json` | Trae 自动识别项目级配置 |
| **AtomCode** | `.mcp.json` | 与 Claude Code 共用同一配置 |
| **Claude Desktop** | 系统级配置目录 | macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`，Windows: `%APPDATA%\Claude\claude_desktop_config.json` |

> 项目 `configs/` 目录下保存了各客户端的参考配置：`cursor_mcp_config.json`、`trae_mcp_config.json`、`claude_desktop_config.json`。

**MCP 客户端官方文档：**

| 客户端 | 官方文档 |
|--------|---------|
| Claude Code | [通过 MCP 将 Claude Code 连接到工具](https://code.claude.com/docs/zh-CN/mcp) |
| Cursor | [Cursor MCP 文档](https://cursor.com/cn/docs/mcp) |
| Trae | [添加 MCP Server](https://docs.trae.cn/ide/add-mcp-servers) |
| AtomCode | [MCP 集成](https://atomcode.atomgit.com/docs/mcp.html) |

#### 支持的传输协议

| 协议 | 端点URL | 说明 |
|------|---------|------|
| **Streamable HTTP** (推荐) | `http://localhost:8765/mcp` | 所有Agent通用，`type: "http"` |
| SSE | `http://localhost:8765/sse` | 旧版协议，部分客户端兼容 |
| stdio | — | 单Agent本地模式，无Web UI，无法多Agent共享 |

#### Skill自动加载（可选便利功能）

项目在 `skills/` 下包含 `register/`、`resume/`、`deregister/` 三个 SKILL.md。以下IDE打开项目时会自动加载Skill，提供 `/dd-register`、`/dd-resume` 和 `/dd-deregister` 命令：

| IDE | Skill目录 |
|-----|----------|
| **Claude Code** | `.claude/skills/` |
| **Cursor** | `.cursor/skills/` |
| **Trae** | `.trae/skills/` |
| **AtomCode** | `.atomcode/skills/` |

> 没有Skill也不影响使用——Agent直接调用MCP工具 `register_agent()` 即可注册。

#### Claude Desktop stdio 模式

> **Claude Desktop 额外支持 stdio 模式**（无需先启动服务器）：
> ```json
> {
>   "mcpServers": {
>     "designdoc": {
>       "command": "uv",
>       "args": ["run", "--directory", "项目绝对路径", "designdoc-mcp", "--transport", "stdio"]
>     }
>   }
> }
> ```
> stdio模式下不需要先运行 `start.ps1`，但**无法使用Web UI**，且多Agent无法共享状态。推荐使用 Streamable HTTP 模式。

#### 工作原理

```
Agent打开项目目录
    ↓
IDE自动加载 .agents/skills/designdoc/SKILL.md
    ↓
IDE通过MCP配置连接到 designdoc 服务器
    ↓
Agent调用 designdoc_guide prompt → 获取协作指南和当前会话状态
    ↓
Agent执行 /dd-register → 注册到会话，自动参与讨论
```

Skill提供三个命令：

| 命令 | 说明 |
|------|------|
| `/dd-register` | 加入会话。无需参数——单session自动加入，多session返回列表选择。注册时自动检测运行时模式 |
| `/dd-resume` | （STEP 模式）推进一步。轮到该 Agent 时（UI 显示 `⏳ needs /dd-resume`）再次运行 |
| `/dd-deregister` | 退出当前会话。无需参数 |

#### 运行时模式与长时执行检测

不同客户端能否"长时间自主循环不断开"差异很大，注册时服务器根据 `client_type` 自动判定 `runtime_mode`：

| 模式 | 适用客户端 | 参与方式 |
|------|-----------|---------|
| `persistent_worker`（LOOP） | `cursor` / `claude_code` / `kimi` / `atomcode`（经压力测试验证） | `wait_for_task(timeout=25)` → `submit_result` 短轮询循环，全程自主 |
| `normal_worker`（STEP） | 其余/`generic`/`trae` 等（保守默认） | 每次唤起只走一步（`heartbeat`→`get_phase_context`→提交），随后停下，由用户 `/dd-resume` 重新唤醒 |

> **检测来源（不依赖 Agent 自报）**：服务端综合 ① MCP 握手的 `clientInfo.name`（如 `Cursor`/`cursor-vscode`/`claude-code`/`Trae`，最权威）、② Agent 传的 `client_type`、③ Agent 名称（如 "Kimi Code CLI"，覆盖握手为通用 `mcp` 的客户端）做关键字归一化。判据集中在 `constants.py` 的 `KNOWN_PERSISTENT_CLIENTS` 与 `CLIENT_TYPE_KEYWORDS`。可用 `register_agent(force_mode="loop"|"step")` 手动覆盖。
>
> 轮询时长 `WAIT_FOR_TASK_TIMEOUT` 默认 25s（建议 20~60s，务必 < 已知客户端单次调用硬上限 300s），有注释可手改。STEP 模式 Agent 在 Web UI 的 Agents 页显示 `STEP` 徽标，轮到它时显示 `⏳ needs /dd-resume`。
>
> **掉线恢复**：断开的 Agent 复用相同 `agent_identity`/名称即可自动 rejoin（即使在 critic/revision 阶段，因为它是"已存在 Agent 回归"而非"新 Agent 加入"）。若辩论卡死（如掉线 Agent 无法回归），可在会话控制栏点击 **Force Human Review** 强制进入人工审核以解锁。

### 4. 开始协作

```
1. [UI] 创建会话，填写标题和需求
2. [Agent] /dd-register <session_id>
3. [Agent] 自动参与讨论（心跳 + 阶段检测 + 内容提交）
4. [UI] 观察流程，在需要时做出决策
5. [UI] 查看文档，归档会话
```

## Web UI

访问 http://localhost:8765 打开Web UI。

### 页面功能

| 页面 | 功能 |
|------|------|
| **Agents** | Agent状态（活跃/离线、心跳时间、视角、模型）+ 需求信息 + 手动注册Agent + 实时事件流 |
| **Flow** | 讨论流程时间线（Proposals→Challenges→Revisions→Optimizations→DA→Votes） |
| **Decisions** | 人类决策界面（假设审核、需求批准、问题解决、辩论审核、最大轮次裁决） |
| **Document** | 设计文档预览 |

### 人类决策

系统在需要人类介入时自动提醒（Toast通知 + 声音 + 浏览器通知）：

| 决策点 | 触发条件 | 操作方式 |
|--------|----------|---------|
| 假设审核 | 澄清阶段Agent分歧 | 点击备选项按钮 |
| 需求批准 | Agent重写需求后 | 点击Approve按钮 |
| 待决问题 | Agent提出问题 | 点击备选项按钮 |
| 共识分歧 | 2+Agent反对 | Approve / Reject / Override |
| 最大轮次 | 达到max_rounds仍未完成 | Approve / Reject / Override |

所有决策都提供备选项，人类只需点击选择。

### 3个主题

🌙 Midnight（深色） / ☀️ Daylight（浅色） / 🔥 Ember（暖色）

## Skill命令详解

### `/dd-register <session_id> [name] [model] [provider] [agent_identity] [client_type]`

注册到指定会话（无需参数，自动检测）。支持 **stable identity 自动 rejoin**：
- 提供 `agent_identity` 时，如果匹配已有 agent，自动恢复（不创建新 agent）
- 适合 Cursor CLI / Claude Code / AtomCode 等支持长时任务的客户端

注册后，每次被唤起时：

1. 调用 `heartbeat(session_id, agent_id)` 保持活跃
2. 调用 `get_phase_context(session_id, agent_id)` 检测当前阶段
3. 根据阶段提交内容

示例：
```
/dd-register
```

### `/dd-deregister`

退出当前会话。

## Agent参与流程

Agent每次被唤起时，按以下逻辑操作：

| 阶段 | 操作 | 推进条件 |
|------|------|---------|
| `clarify_identify` | `submit_assumptions` — 独立提交假设 | 全部Agent提交后自动推进 |
| `clarify_refine` | `supplement_assumption_options` — 补充备选项 | 全部Agent提交后自动推进 |
| `clarify_review` | 等待人类审核 | 人类审核后推进 |
| `clarify_rewrite` | `submit_refined_requirement` — 重写需求 | 全部Agent提交后，人类批准后推进 |
| `proposal` | `submit_proposal` — 从分配的视角提出方案 | 全部Agent提交后自动推进 |
| `critic` | `submit_challenge` — 挑战其他方案 | 全部Agent提交后自动推进 |
| `revision` | `submit_revision` — 根据反馈修订 | 全部Agent提交后自动推进 |
| `optimization` | `submit_optimization` — 提出优化 | 全部Agent提交后自动推进 |
| `devils_advocate` | `submit_devils_advocate` — 魔鬼代言人分析 | 至少1人提交后自动推进 |
| `consensus` | `cast_consensus_vote` — 投票 |
| `human_review` | 等待人类决策 |

## 需求清晰度评估

提交需求时系统自动评估清晰度（0.0~1.0），基于10个维度关键词匹配：

- **清晰度 ≥ 0.7** → 自动跳过澄清，直接进入辩论
- **清晰度 < 0.7** → 进入4阶段澄清流程

评分规则：基础分(覆盖维度/10) + 长度加分(max 0.15) + 字段加分(每个非空字段+0.05)

## 4层输出

辩论完成后，系统生成4份文档：

1. **设计文档** — 面向开发的结构化设计文档
2. **ADR** — 架构决策记录
3. **辩论摘要** — 关键挑战、改进、事件时间线
4. **人工决策点** — 分歧假设、待决问题、高风险项

## Docker部署

```bash
docker compose up -d
```

服务将在 http://localhost:8765 提供Web UI和MCP端点。

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DESIGNDOC_DATA_DIR` | `~/.designdoc_mcp` | 数据存储目录 |
| `DESIGNDOC_TRANSPORT` | `stdio` | 传输协议 (stdio/sse/http/streamable-http) |
| `DESIGNDOC_HOST` | `0.0.0.0` | 监听地址 |
| `DESIGNDOC_PORT` | `8765` | 监听端口 |
| `DESIGNDOC_API_TOKEN` | 空 | API认证Token（空=不启用） |
| `DESIGNDOC_STORAGE` | `json` | 存储后端类型 (json/sqlite) |
| `DESIGNDOC_NO_WEB` | 空 | 设为`1`禁用Web UI |
| `DESIGNDOC_LOG_DIR` | 空 | 日志文件目录（空=默认写入项目根目录 `logs/`） |

## 技术栈

- **Python 3.10+** + **FastMCP >=2.0** (MCP服务器框架)
- **FastAPI** (Web UI + REST API)
- **Pydantic 2.x** (数据模型与校验)
- **文件持久化** + 文件锁 (并发安全) / **SQLite** (可选存储后端)
- **Streamable HTTP传输** (多Agent共享连接 + 实时事件推送)
- **Alpine.js + Tailwind CSS** (Web UI，零构建步骤)

## 项目文档

| 文档 | 说明 |
|------|------|
| [docs/specification.md](docs/specification.md) | 技术规格 — 项目实现的唯一权威参考 |
| [docs/design-v1.md](docs/design-v1.md) | 原始设计文档 — 项目初始设计蓝图 |
| [docs/decision-points.md](docs/decision-points.md) | 按分歧点决策功能规划 |
| [docs/issues.md](docs/issues.md) | 问题跟踪与实现规划 |
| [docs/restructure.md](docs/restructure.md) | 架构重构方案 |
