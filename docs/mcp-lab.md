# MCP Compatibility Lab

Standalone test servers for validating MCP protocol compatibility across different agents.

**Scope:** Experimental infrastructure only.  
**Does NOT depend on** DesignDocMCP runtime.  
**Does NOT affect** the main MCP server.

---

## Servers

| Server | Port | Endpoint | Transport | Purpose |
|--------|------|----------|-----------|---------|
| A — HTTP | 9101 | `/mcp` | StreamableHTTP only | Validate StreamableHTTP clients |
| B — SSE | 9102 | `/sse` | SSE only | Validate SSE clients |
| C — Dual | 9103 | `/mcp` + `/sse` | StreamableHTTP + SSE | Simulate final compatibility target |

Server A explicitly **does not** expose `/sse`.  
Server B explicitly **does not** expose `/mcp`.  
Server C exposes **both**.

---

## Tools (all servers share the same deterministic toolset)

| Tool | Input | Output |
|------|-------|--------|
| `ping()` | — | `"pong"` |
| `echo(text)` | `"hello"` | `"hello"` |
| `multiply(a, b)` | `3, 4` | `12` |

No other tools are registered.  
Tool behavior is fully deterministic and stateless.

---

## Startup

### Start all three servers

```bash
uv run python scripts/start_mcp_lab.py --all
```

Expected output:

```
============================================================
MCP Compatibility Lab
============================================================
[HTTP] running at http://localhost:9101/mcp
[SSE] running at http://localhost:9102/sse
[DUAL] running at http://localhost:9103/mcp + /sse
------------------------------------------------------------
Press Ctrl+C to stop all servers
============================================================
```

### Start individual servers

```bash
uv run python scripts/start_mcp_lab.py --http   # port 9101 only
uv run python scripts/start_mcp_lab.py --sse    # port 9102 only
uv run python scripts/start_mcp_lab.py --dual   # port 9103 only
uv run python scripts/start_mcp_lab.py --http --sse  # ports 9101 + 9102
```

---

## Quick Tests

### StreamableHTTP quick test (Server A or C)

Initialize a session:

```bash
curl -s -D - -X POST http://localhost:9101/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "lab-test", "version": "1.0"}
    }
  }'
```

Expected:

* HTTP `200 OK`
* Header `mcp-session-id: <uuid>`
* SSE-formatted JSON-RPC `InitializeResult`

List tools with the returned session ID:

```bash
curl -s -X POST http://localhost:9101/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -H 'mcp-session-id: <uuid-from-above>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
  }'
```

Expected: JSON-RPC result containing `ping`, `echo`, `multiply`.

### SSE quick test (Server B or C)

Open the SSE stream:

```bash
curl -s -N -H "Accept: text/event-stream" http://localhost:9102/sse
```

Expected (first event):

```
event: endpoint
data: /messages/?session_id=<uuid>
```

Use the returned `session_id` to send an `InitializeRequest` via POST to `/messages/?session_id=<uuid>`.

---

## Notes

* Servers bind to `0.0.0.0` — accessible from the local network.
* Logs are suppressed (`log_level=warning`, `access_log=False`) to reduce noise during compatibility testing.
* Servers are stateless except for the session IDs created by FastMCP.
