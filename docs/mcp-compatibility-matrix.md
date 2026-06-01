# MCP Compatibility Matrix

## cursor

### Effective mcp config paths

| Level | Path | Loaded | Evidence |
|---|---:|---:|---|
| Global (user) | `C:\Users\Administrator\.cursor\mcp.json` | Yes | Cursor 日志 `createClient: identifier="user-designdoc"`（`workbench.mcp.files.log` 2026-06-01） |
| Project (workspace) | `E:\DesignDocMCPTest1\.cursor\mcp.json` | Yes | 日志 `project-0-DesignDocMCP-designdoc`（`workbench.mcp.oauth.log` / `Mcp FileSystem Writer.log`） |
| `.kimi/mcp.json` | `E:\DesignDocMCPTest1\.kimi\mcp.json` | No（Cursor） | 文件存在；Cursor MCP 日志无 kimi 相关 server 标识 |
| `.trae/mcp.json` | `E:\DesignDocMCPTest1\.trae\mcp.json` | No（Cursor） | 同上 |
| Plugin 内置 | Marketplace 插件根 `mcp.json` | Yes | `plugin-context7-context7` 等出现在 lease / MCP 日志 |

**Project-level：** 支持（`.cursor/mcp.json`）。

**Global-level：** 支持（`~/.cursor/mcp.json`）。

**Precedence：** 官方文档为「合并加载；同名 server 以 project 覆盖 global」。实测同名 `designdoc` 时仍可能出现 `user-designdoc` 与 `project-0-DesignDocMCP-designdoc` 两个标识符（均加载，配置内容可不同）。

---

### Schema compatibility

| Schema | Result | Notes |
|---|---:|---|
| A — `{ "url": "..." }` | PASS | JSON 合法；协议测试 `initialize` / `tools/list` / `tools/call` 对 `http://localhost:9101/mcp` 全部成功 |
| B — `{ "type": "http", "url": "..." }` | PASS | 与当前 project `.cursor/mcp.json` 格式一致；日志证实 project 级配置被加载 |
| C — `{ "transport": "http", "url": "..." }` | PASS* | JSON 合法；`transport` 非官方字段，推断由 `url` 驱动远程连接；协议测试不受阻。建议生产仍用 A/B |

\*C 为兼容性通过（协议层），非官方推荐写法。

---

### Protocol compatibility

| Protocol | Connect | Tool list | Tool call | Reconnect | Notes |
|---|---:|---:|---:|---:|---|
| StreamableHTTP (`9101` `/mcp`) | PASS | PASS | PASS | PASS | `echo("hello")`→`hello`；`multiply(3,4)`→`12`；需 `Mcp-Session-Id` 后续请求 |
| SSE (`9102` `/sse`) | PASS | PASS | PASS | PASS | 需保持 `GET /sse` 长连接；消息走 `POST /messages/?session_id=...`；响应经 SSE 回流 |
| Dual (`9103` `/mcp`) | PASS | PASS | PASS | PASS | 配置 `url: .../mcp` 时走 Streamable HTTP，稳定 |
| Dual (`9103` `/sse`) | PASS* | PASS* | PASS* | PASS* | 模拟 Cursor：`POST /sse`→405，再 `GET /sse`→`endpoint` 事件后 SSE 流程可用；配置应优先 `/mcp` |

**Dual 模式 Cursor 选型（实测 + 日志模式）：**

- 对 `http://localhost:9103/mcp`：**Streamable HTTP**（`POST` 200 + session）。
- 对 `http://localhost:9103/sse`：先尝试 Streamable HTTP（`POST`→**405**），再 **fallback SSE**（与 `MCP user-designdoc.log` 中 “streamableHttp → SSE” 一致）。

**Reconnect（9101）：** 停止 lab 进程后 `tools/list` 失败；重启 `uv run python scripts/start_mcp_lab.py --all` 后重新 `initialize` 成功（协议层 PASS）。本 agent 会话内未观测 Cursor IDE 无刷新自动重连；需在 Settings/MCP 或重载窗口后恢复。

---

### Final Verdict

Prefer:

- StreamableHTTP

Reason:

本地 lab 在 `9101`/`9103/mcp` 上 Streamable HTTP 单连接即可完成 initialize、tools/list、echo、multiply，且 reconnect 后协议可恢复。`9102` 纯 SSE 需双通道（`GET /sse` + `POST /messages`），复杂且对长连接更敏感。Dual 服务在 `/mcp` 路径下与 Streamable HTTP 等价稳定；`/sse` 路径仅适合兼容旧服务端。Cursor 运行时优先 Streamable HTTP，失败再 SSE fallback，因此配置应使用 `url` 指向 `.../mcp`，省略非标准 `transport` 字段。

---

## Claude Code

PENDING

---

## Kimi

PENDING

---

## AtomCode

PENDING

---

## Trae

PENDING
