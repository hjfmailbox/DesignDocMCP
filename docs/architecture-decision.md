# Architecture Decision: From Persistent Worker to Orchestrator Invocation

## Status

**Decision**: Accepted  
**Date**: 2026-06-02  
**Tag**: `pre-orchestrator-refactor` (`546831c`)  

## Context

`probe_mcp` (MiniDebateRuntime) was built to validate whether multiple AI agents could participate in a coordinated debate workflow driven by an MCP server. The original architecture assumed:

- Agents register once and persist
- Server pushes phase transitions via MCP `notifications/message`
- Agents wait in a loop (`wait_for_task` or push-handler) for the next instruction
- Long-running sessions with barrier synchronization

## Empirical Results

### Verified Capabilities

| Capability | Evidence | Status |
|---|---|---|
| MCP `register_agent` | Successful registration across Claude Code, Cursor, Trae, Kimi | ✅ Verified |
| Multi-client compatibility | 4 distinct client types can connect to same session | ✅ Verified |
| Notification transport | `ss.Log()` delivery confirmed via Go SDK e2e_test | ✅ Verified |
| Loop technically works | `dd-enter-auto-mode` skill enters push loop correctly | ✅ Verified |

### Falsified Capabilities

| Capability | Evidence | Status |
|---|---|---|
| MCP push wakes agent reasoning | Session logs show **zero** received notifications in skill context | ❌ Falsified |
| Notification = auto execution | Agent enters loop but never triggers submit on push | ❌ Falsified |
| Long-running `wait_for_task` | Streamable-http idle timeout drops connection during wait | ❌ Falsified |
| Persistent worker stable | Client sessions terminate unpredictably; no reconnect protocol | ❌ Falsified |

### Root Cause

MCP `notifications/message` (logging notification) is received at the **client transport layer** but is **not routed to the active skill execution context** in Claude Code or Cursor. The skill waits indefinitely; the notification is either dropped or handled by a separate handler invisible to the skill.

## Decision

Abandon the persistent-worker + push-notification architecture. Replace with:

> **Orchestrator-driven, one-shot agent invocation.**

## Consequences

### What We Keep

- Session Store (state management)
- Task Queue (per-phase task generation)
- Result Store (submission tracking)
- Phase Controller (barrier advancement logic)
- Multi-agent topology (challenge pairing, etc.)

### What We Discard

- `wait_for_task` loop
- Timeout/retry loop for push delivery
- Persistent worker concept
- Dependency on MCP notification push for agent wakeup
- `dd-enter-auto-mode` push-based skill (to be replaced)

### What We Add

- Orchestrator component that drives phase transitions externally
- One-shot execution contract: agent invoked once, submits, exits
- CLI invocation pattern for each agent
- Polling interface (as fallback) for clients that cannot be orchestrated

## Agent Execution Contract (New)

```text
orchestrator
    │  "session X needs agent Y to submit_phase_Z"
    ▼
spawn agent process
    │  claude -p "/dd-execute <session_id> <agent_id> <phase>"
    ▼
agent executes once
    │  calls register_agent (idempotent)
    │  calls submit_<phase>
    │  calls get_runtime_status (optional)
    ▼
agent exits immediately
    │
    ▼
orchestrator observes barrier state
    │  all agents submitted? → advance phase
    ▼
repeat for next phase
```

## Future Work

- Session Store, Task Queue, Result Store may be extracted to standalone services
- Orchestrator may become a separate process or Kubernetes Job controller
- This design supports 4+ agents because invocation is stateless and parallelizable
