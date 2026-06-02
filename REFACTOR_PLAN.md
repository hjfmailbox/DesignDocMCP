# REFACTOR_PLAN: DesignDocMCP Orchestrator Architecture

## Status

Phase: **Design + Skeleton Only** — Implementation NOT started.
Freeze tag: `pre-orchestrator-refactor` (`546831c`)

---

## 1. New Architecture Design

### 1.1 Core Principle

Agent is **stateless, non-resident, non-looping**.

```text
┌─────────────────────────────────────────────────────────────┐
│                      Orchestrator                            │
│  (drives phase lifecycle, observes barrier, spawns agents)  │
└──────────────────┬──────────────────────────────────────────┘
                   │ spawn
                   │ "claude -p /dd-execute <sess> <agent> <phase>"
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Agent Process (one-shot, ephemeral)                         │
│                                                              │
│  1. register_agent (idempotent)                             │
│  2. submit_<phase> (with task_id + content)                 │
│  3. get_runtime_status (confirm)                            │
│  4. EXIT                                                    │
└─────────────────────────────────────────────────────────────┘
                   │ submit_result
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Session Store + Task Queue + Result Store                   │
│  (MiniDebateRuntime, keep barrier logic)                     │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Phase Advancement Flow

```text
Phase N begins
    │
    ▼
Orchestrator generates tasks for all agents in Phase N
    │
    ▼
For each agent:
    spawn(agent, "submit_" + phase)
    │
    ▼
Agent submits → Result Store updated
    │
    ▼
Orchestrator polls barrier (or receives callback)
    │
    ▼
All active agents responded?
    │ yes ──► advance to Phase N+1
    │ no  ──► wait / retry unresponsive agents
```

### 1.3 What Changes, What Stays

| Component | Before | After | Action |
|---|---|---|---|
| Session Store | `MultiAgentSession` in memory | Same, keep | Keep |
| Task Queue | `PhaseTask` generated per phase | Same, keep | Keep |
| Barrier | `checkBarrier()` in scheduler | Same logic, caller changes | Keep |
| Phase Controller | `scheduler.go` tick loop | Extracted into Orchestrator | Refactor |
| Push Delivery | `ss.Log()` notifications | **Delete** | Remove |
| Agent Skill | `dd-enter-auto-mode` push loop | `dd-execute` one-shot | Replace |
| Worker Model | Persistent, waiting | Ephemeral, one-shot | Replace |
| Orchestrator | N/A | New component | Add |

---

## 2. Directory Restructure

```text
probe_mcp/
├── cmd/
│   └── mini-debate-runtime/
│       └── main.go              # Entry: server mode or orchestrator mode
├── pkg/
│   ├── server/
│   │   ├── server.go            # MCP tool handlers (register, submit, status)
│   │   └── tools.go             # Tool registration
│   ├── state/
│   │   ├── session.go           # MultiAgentSession, Agent, PhaseTask
│   │   ├── crud.go              # getSession, getOrCreateSessionForAgent
│   │   └── barrier.go           # Barrier check logic
│   ├── phase/
│   │   ├── controller.go        # enterPhase, generateTasks
│   │   └── tasks.go             # Per-phase task generation
│   ├── orchestrator/
│   │   ├── orchestrator.go      # Orchestrator struct and Run()
│   │   ├── spawn.go             # Agent spawn abstraction
│   │   └── observer.go          # Barrier polling / result observation
│   ├── logger/
│   │   └── logger.go            # Structured JSONL logging
│   └── api/
│       └── admin.go             # HTTP handlers + UI
├── internal/
│   └── e2e/
│       └── e2e_test.go          # End-to-end test
├── web/
│   └── ui.go                    # Embedded HTML UI
└── docs/
    └── architecture-decision.md

skills/
├── dd-register/
│   └── SKILL.md                 # (keep, idempotent registration)
├── dd-execute/
│   └── SKILL.md                 # NEW: one-shot execution skill
└── dd-probe/
    └── SKILL.md                 # (keep for transport diagnostics)
```

**Notes:**
- `scheduler.go` **deleted** — replaced by `orchestrator/`
- `phases.go` **moved** to `pkg/phase/`
- `admin.go` **moved** to `pkg/api/`
- `dd-enter-auto-mode` **replaced** by `dd-execute`

---

## 3. Core Components

### 3.1 Orchestrator (`pkg/orchestrator/`)

Responsibilities:
- Own the session lifecycle (create → run phases → complete)
- Generate tasks for each phase
- Spawn agent processes for each task
- Observe results (poll barrier or callback)
- Advance phase when barrier clears
- Handle degraded agents (retry or skip)

Interface (tentative):

```go
type Orchestrator struct {
    SessionStore *state.Store
    Spawner      Spawner
    Observer     Observer
}

func (o *Orchestrator) RunSession(sessionID string) error
func (o *Orchestrator) advancePhase(sess *state.MultiAgentSession) error
func (o *Orchestrator) spawnForTask(task *state.PhaseTask) error
```

### 3.2 Spawner (`pkg/orchestrator/spawn.go`)

Responsibilities:
- Abstract over "how to invoke an agent"
- Support multiple backends:
  - `CLI Spawner`: exec `claude -p "/dd-execute ..."`
  - `HTTP Spawner`: POST to agent webhook
  - `Mock Spawner`: for testing

```go
type Spawner interface {
    Spawn(sessionID, agentID, phase, taskID string) error
}
```

### 3.3 Observer (`pkg/orchestrator/observer.go`)

Responsibilities:
- Check if all active agents have submitted for current phase
- Detect timeout / degradation
- Trigger phase advance

```go
type Observer interface {
    WaitForBarrier(sessionID string, timeout time.Duration) (bool, error)
}
```

### 3.4 Server (`pkg/server/`)

Responsibilities:
- MCP tool handlers (unchanged logic, simplified):
  - `register_agent` — idempotent, store ServerSession
  - `submit_proposal/challenge/revision/consensus` — mark task responded
  - `get_runtime_status` — return phase + needs_submit
- No push logic. No notification logic.

### 3.5 Agent Skill: `dd-execute`

Behavior:
- Called as: `/dd-execute <session_id> <agent_id> <phase>`
- Steps:
  1. `register_agent` (idempotent, returns existing if present)
  2. `get_runtime_status` (verify phase matches expected)
  3. `submit_<phase>` (with empty or minimal content)
  4. Print result and exit
- No loop. No wait. No push handler.

---

## 4. Data Flow

```text
┌─────────────┐     register      ┌──────────────┐
│   Agent A   │ ────────────────► │              │
└─────────────┘                   │   Session    │
                                  │   Store      │
┌─────────────┐     register      │              │
│   Agent B   │ ────────────────► │              │
└─────────────┘                   └──────┬───────┘
                                         │
                    ┌────────────────────┘
                    │
                    ▼
           ┌──────────────┐
           │ Orchestrator │ ◄── user or cron triggers start
           └──────┬───────┘
                  │ spawn Agent A (submit_proposal)
                  │ spawn Agent B (submit_proposal)
                  ▼
           ┌──────────────┐
           │   Barrier    │
           │   Observer   │ ◄── polls until all responded
           └──────┬───────┘
                  │ barrier clear
                  ▼
           ┌──────────────┐
           │ Phase Advance│ ◄── enter CHALLENGE, generate tasks
           └──────────────┘
                  │
                  │ spawn Agent A (submit_challenge)
                  │ spawn Agent B (submit_challenge)
                  ▼
                ... repeat until COMPLETE
```

---

## 5. Acceptance Criteria

### 5.1 Architecture Compliance

- [ ] **No `wait_for_task` loop** anywhere in codebase
- [ ] **No persistent worker** concept (no long-running agent process)
- [ ] **No notification dependency** (MCP push not required for correctness)
- [ ] **Agent lifecycle = one execution → exit**
- [ ] **Orchestrator drives phase advancement** (not agent self-coordination)
- [ ] **Supports 4+ agents** without architectural change

### 5.2 Functional

- [ ] `dd-execute` skill completes in < 10 seconds per phase
- [ ] Orchestrator can run a 2-agent session end-to-end
- [ ] Orchestrator can run a 4-agent session end-to-end
- [ ] Degraded agent does not block phase advance
- [ ] Session result written to disk on COMPLETE

### 5.3 Testability

- [ ] `MockSpawner` allows e2e test without real agent processes
- [ ] `MockObserver` allows deterministic barrier testing
- [ ] All existing e2e tests pass after refactor

---

## 6. Out of Scope (Explicit)

The following are **NOT** part of this refactor:

- **Distributed orchestrator** (multi-node, Kubernetes) — keep single-process
- **Real argument generation** — agents still submit `{}` or minimal content
- **Dynamic topology** — keep fixed challenge pairing
- **Agent reconnection** — one-shot, no reconnect needed
- **UI rewrite** — keep existing admin UI, add orchestrator status page only
- **Config file / env var overhaul** — use existing constants

---

## 7. Implementation Sequence (Future)

When implementation begins, recommended order:

1. **Skeleton** — create `pkg/orchestrator/`, `pkg/phase/`, move files
2. **Server cleanup** — remove push logic from `pkg/server/`
3. **Orchestrator core** — `RunSession`, `advancePhase`, `spawnForTask`
4. **Spawner interface** — `CLISpawner` and `MockSpawner`
5. **Observer** — poll-based barrier observation
6. **`dd-execute` skill** — replace `dd-enter-auto-mode`
7. **e2e test** — mock-based end-to-end
8. **Integration** — real agent spawn test

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Agent spawn latency adds overhead | Spawn is parallel; each phase still parallelizable |
| CLI invocation varies by client | Spawner abstraction supports per-client command templates |
| Agent fails to register before submit | `register_agent` is idempotent; skill retries once |
| Orchestrator crashes mid-session | Session state is in-memory only (acceptable for v1) |

---

*End of REFACTOR_PLAN.md*
