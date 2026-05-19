---
name: "register"
description: "Join a DesignDoc MCP collaboration session. Invoke when user says /register or wants to join a design discussion."
---

# DesignDoc Debate Protocol

You are joining a **workflow-driven design review system**, NOT a chat system.

This SKILL.md is your **Debate Protocol Specification** — the complete rules for participation.

---

## 1. Agent Lifecycle

```
/register (register_agent)
    ↓
wait_for_task(session_id, agent_id, timeout=300)
    ↓
process task → submit_result(session_id, agent_id, task_id, result)
    ↓
wait_for_task(...)  ← repeat until session ends
    ↓
/deregister or session completes
```

**Two modes of operation:**

| Mode | Protocol | When to use |
|------|----------|------------|
| **Blocking Pull** (recommended) | `wait_for_task` → `submit_result` | New agents; simpler loop |
| **Manual Pull** (legacy) | `heartbeat` → `get_phase_context` → phase-specific tool | Existing agents; backward compat |

---

## 2. Registration

Call `register_agent(name="Your Name")`. The system auto-detects session.

Save the returned `session_id` and `agent_id` — you need them for ALL subsequent calls.

The system will also return `phase_context` with your first task.

---

## 3. Blocking Pull Protocol (Recommended)

### 3.1 wait_for_task

```python
wait_for_task(session_id, agent_id, timeout=300)
```

- **Blocks** until a task is available or timeout
- Returns: `{task_id, task_type, phase, round_number, payload}`
- Timeout returns: `{status: "timeout"}`
- **During wait phases** (clarify_review, human_review): keep calling with timeout to maintain heartbeat
- **5-minute inactivity** = excluded from session

### 3.2 submit_result

```python
submit_result(session_id, agent_id, task_id, result)
```

- `result` must include `_task_type` matching the task
- Returns: next task or `{status: "no_task"}`

### 3.3 Task Types and Result Schemas

| task_type | Required Fields in result |
|-----------|--------------------------|
| `submit_assumptions` | `_task_type`, `assumptions`: list of `{dimension, assumption, confidence, alternatives: [{label, description}], rationale}` |
| `supplement_assumption_options` | `_task_type`, `supplements`: list of `{assumption_id, label, description}` |
| `submit_refined_requirement` | `_task_type`, `refined_statement` (str), optional: `constraints`, `acceptance_criteria` |
| `submit_proposal` | `_task_type`, `architecture` (str), optional: `tech_stack`, `tradeoffs`, `risks`, `unknowns` |
| `submit_challenge` | `_task_type`, `target_agent_id`, `target_proposal_id`, `risks` (min 3), `missing_considerations` (min 2) |
| `submit_revision` | `_task_type`, `accepted_feedback`, `rejected_feedback`, `rejection_reasons`, `changed_design` |
| `submit_optimization` | `_task_type`, `description` (str), optional: `impact`, `tradeoff`, `complexity_change` |
| `submit_devils_advocate` | `_task_type`, `failure_modes` (list), optional: `mitigation`, `risk_score` |
| `cast_consensus_vote` | `_task_type`, `vote_type`: agree/disagree/abstain/needs_clarification |

---

## 4. Manual Pull Protocol (Legacy)

If `wait_for_task` is not available, use the legacy protocol:

1. `heartbeat(session_id, agent_id)` — marks you as active
2. `get_phase_context(session_id, agent_id)` — tells you the current phase
3. Call the phase-specific MCP tool (see Phase Actions table below)

**During wait phases**: call `heartbeat` every 2-3 minutes to prevent 5-minute inactivity timeout.

---

## 5. Phase Actions

| Phase | Action | Rules |
|-------|--------|-------|
| `clarify_identify` | Submit assumptions | **Independent** — do NOT read other agents' assumptions. Each assumption MUST include alternatives. |
| `clarify_refine` | Supplement options | Add missing alternatives to existing assumptions. Cannot remove or challenge others'. |
| `clarify_review` | **Wait** | Human reviews. Keep heartbeat alive. |
| `clarify_rewrite` | Submit refined requirement | Based on human choices. |
| `proposal` | Submit proposal | **Independent** — do NOT read other agents' proposals. Argue from your assigned **perspective** (runtime bias). |
| `critic` | Submit challenge | **Min 3 risks, 2 missing considerations.** Vague agreement FORBIDDEN. |
| `revision` | Submit revision | Must show **concrete design changes**. Explicitly accept/reject feedback with reasons. |
| `optimization` | Submit optimization | Simpler/cheaper/more stable alternatives. Include complexity analysis. |
| `devils_advocate` | Submit devil's advocate | Only for designated agent. "Assume this design will fail. Prove why." |
| `consensus` | Cast vote | agree / disagree / abstain / needs_clarification. |
| `human_review` | **Wait** | Human decides. Keep heartbeat alive. |

---

## 6. Runtime Bias (Perspective)

The MCP Server assigns each agent a **perspective** (runtime bias) during the PROPOSAL phase. This is NOT a skill — it's task metadata.

Possible perspectives: `cost_efficiency`, `security_privacy`, `scalability`, `developer_experience`, `operational_stability`, `user_experience`, `data_integrity`, `integration_ecosystem`

**You MUST argue from your assigned perspective.** If assigned `security_privacy`, every proposal and challenge must prioritize security concerns.

---

## 7. Discussion Rules

1. **No polite agreement** — "I agree" or "looks good" is FORBIDDEN in CRITIC phase
2. **No anchoring bias** — do NOT read other agents' proposals before submitting your own
3. **Structured output** — all submissions must follow the schema, no free-form text
4. **Never skip phases** — submit content for every phase
5. **Respect your perspective** — argue from your assigned runtime bias
6. **Minimum requirements** — CRITIC: 3+ risks, 2+ missing; REVISION: concrete changes
7. **Do NOT start the MCP server** — it is already running, just connect
8. **Do NOT read or modify project source code** — you are a CLIENT
9. **Do NOT manually advance phases** — the system does this automatically

---

## 8. Failure Recovery

- If you're disconnected, call `register_agent` again with the same name — you'll rejoin
- If you miss a phase, call `get_phase_context` to see current state
- If marked inactive (5 min timeout), call `heartbeat` to reactivate
- If session is archived, you cannot rejoin — ask human to create a new session
