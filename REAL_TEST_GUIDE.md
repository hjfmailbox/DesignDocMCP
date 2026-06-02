# Real 2-Agent Test Guide

**Goal**: Run one full debate with Claude Code + Cursor CLI as real agents.

---

## Prerequisites

1. **MiniDebateRuntime built**
   ```powershell
   cd D:\Codes\Personal\DesignDocMCP\probe_mcp
   go build ./cmd/mini-debate-runtime
   ```

2. **Claude Code** installed and in PATH (`claude` command works)

3. **Cursor CLI** installed (`agent.ps1` at `C:\Users\Administrator\AppData\Local\cursor-agent\agent.ps1`)

4. **Both clients configured** to connect to MiniDebateRuntime MCP server at `http://127.0.0.1:8799/mcp`

---

## Test Steps

### Step 1 — Start Orchestrator Mode

Open **Terminal 1** and run:

```powershell
cd D:\Codes\Personal\DesignDocMCP\probe_mcp
.\mini-debate-runtime.exe -mode orchestrator -spawner cli -delay 15 -session auto
```

Flags:
- `-mode orchestrator` — Start HTTP server + orchestrator (no scheduler tick)
- `-spawner cli` — Use CLISpawner (spawns real `claude` / `agent` processes)
- `-delay 15` — Wait 15 seconds for agents to register before starting debate
- `-session auto` — Auto-discover the first active session

You will see:
```
Orchestrator waiting 15s for agents to register...
```

### Step 2 — Register Agent 1 (Claude Code)

Open **Terminal 2** and run:

```powershell
claude -p "/dd-register"
```

This should:
- Call `register_agent(client="claude-code", model="claude-sonnet")`
- Return `agent_id` and `session_id`
- Print something like: `Agent claude-code_... registered in session sess_...`

### Step 3 — Register Agent 2 (Cursor CLI)

Open **Terminal 3** and run:

```powershell
cd e:\DesignDocMCPTest1
agent -p "/dd-register" --yolo
```

This should:
- Call `register_agent(client="cursor", model="gpt-4")`
- Join the **same session** as Agent 1 (because session is in REGISTERED phase with room)

### Step 4 — Watch Orchestrator Drive the Debate

Back in **Terminal 1**, after the 15-second delay, the orchestrator will:

1. Enter **PROPOSAL** phase
2. Spawn Claude Code: `claude -p "/dd-execute PROPOSAL task_..."`
3. Spawn Cursor CLI: `powershell -Command "agent -p '/dd-execute PROPOSAL task_...' --yolo"`
4. Wait for barrier (both agents submit)
5. Enter **CHALLENGE** phase
6. Spawn both agents again
7. Repeat for REVISION and CONSENSUS
8. Mark session **COMPLETE**

Each spawned agent will:
- Call `register_agent` (idempotent, returns existing agent)
- Call `submit_<phase>`
- Exit immediately

### Step 5 — Verify Results

Check Terminal 1 output for:
```
Orchestrator finished session successfully.
```

Check the session report:
```powershell
Get-Content "E:\DesignDocMCPTest1\probe_outputs\<session_id>\summary.json" | ConvertFrom-Json
```

Expected:
```json
{
  "result": "PASS",
  "completed": true,
  "phases": {
    "PROPOSAL": true,
    "CHALLENGE": true,
    "REVISION": true,
    "CONSENSUS": true
  }
}
```

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `agent` command not found | Use full path: `powershell -Command "& 'C:\Users\Administrator\AppData\Local\cursor-agent\agent.ps1' -p '/dd-register' --yolo"` |
| Session not found | Ensure both agents register within the 15-second delay window |
| Agents join different sessions | They must use different `client` or `model` values; same client+model triggers idempotency and returns the same agent |
| Submit fails with "unknown_task" | The agent was spawned before the task was created; this shouldn't happen with the delay + auto-discover flow |
| Orchestrator times out in a phase | Check agent logs in Terminal 2 and 3 for MCP connection errors |

---

## What This Proves

- Orchestrator can drive a real debate with external AI agents
- Agent lifecycle is truly one-shot (spawn → submit → exit)
- No persistent worker or push loop required
- Claude Code and Cursor CLI can interoperate via the same MCP server
