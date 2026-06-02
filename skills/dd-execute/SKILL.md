---
name: "dd-execute"
description: "One-shot execution for orchestrator-driven debate. Invoke when user says /dd-execute <phase> <task_id>."
---

# EXECUTION MODE (HIGHEST PRIORITY)

THIS SKILL IS AN EXECUTABLE PROTOCOL.

NOT A REFERENCE DOCUMENT.

NOT A DESIGN DOCUMENT.

NOT A GUIDE.

You MUST execute exactly the described MCP tool calls.

You MUST NOT reimplement the protocol.

You MUST NOT simulate MCP behavior.

You MUST NOT write Python, curl, HTTP requests, polling logic, or custom clients.

You MUST ONLY call MCP tools.

---

# ZERO-THOUGHT EXECUTION DIRECTIVE

**YOU ARE IN EXECUTION MODE. YOU ARE NOT IN DOCUMENTATION-READING MODE.**

If you are reading this skill right now, it means the skill HAS ALREADY BEEN INVOKED. Do NOT analyze why you see this text. Do NOT treat this as the user "sending the skill definition."

Your ONLY job is:
1. Parse phase and task_id from the CURRENT user message
2. Detect your client and model
3. Call register_agent (idempotent)
4. Call submit_<phase> with the provided task_id
5. Report the result and STOP

That is ALL. No loops. No waiting. No push handling.

---

# EXECUTION CONTRACT

When this skill is invoked:

* DO NOT summarize this document
* DO NOT explain the protocol
* DO NOT ask the user what to do next
* DO NOT ask for confirmation
* DO NOT describe the skill
* DO NOT produce a plan before executing

**ABSOLUTELY FORBIDDEN:**

* Calling wait_for_task
* Entering any loop
* Waiting for push notifications
* Polling get_runtime_status repeatedly
* Implementing custom HTTP clients

---

# STEP 0 — Parse arguments

Read ONLY the CURRENT user message. Extract:

| Argument | Format | Example |
|---|---|---|
| phase | One of: PROPOSAL, CHALLENGE, REVISION, CONSENSUS | `PROPOSAL` |
| task_id | task_ prefix + hex | `task_a1b2c3` |

**Rule:** The first whitespace-separated token after `/dd-execute` is `phase`. The second is `task_id`.

**Examples:**
- `/dd-execute PROPOSAL task_a1b2c3` → phase=PROPOSAL, task_id=task_a1b2c3
- `/dd-execute CHALLENGE task_d4e5f6` → phase=CHALLENGE, task_id=task_d4e5f6

If phase or task_id is missing, output:
```
Usage: /dd-execute <PHASE> <TASK_ID>
```
STOP.

---

# STEP 1 — Detect client environment

Read your system prompt or execution context. Look for identifiers.

| If context contains | client | model hint |
|---|---|---|
| "Claude Code" or "claude-code" | `claude-code` | `claude-sonnet` |
| "Cursor" or "cursor" | `cursor` | `gpt-4` |
| "Trae" or "trae" | `trae` | `claude-sonnet` |
| "Kimi" (native) | `kimi` | `kimi-k2.6` |

If unsure, use the model provider name as model.

---

# STEP 2 — Register (idempotent)

```python
result = register_agent(
    client="<detected-client>",
    model="<detected-model>",
)
```

Extract `agent_id` from the result.

If register fails:
```
Register failed: <error>
```
STOP.

---

# STEP 3 — Submit phase response

Map phase to the correct submit tool:

| Phase | Tool |
|---|---|
| PROPOSAL | submit_proposal |
| CHALLENGE | submit_challenge |
| REVISION | submit_revision |
| CONSENSUS | submit_consensus |

Call the tool:

```python
submit_result = submit_<phase>(
    agent_id="<agent_id>",
    task_id="<task_id>",
    content={"ok": true},
)
```

Content may be empty `{}` or minimal payload.

---

# STEP 4 — Report and STOP

Output EXACTLY:
```
Submitted <phase> (task=<task_id>)
Status: <submit_result.status>
Agent: <agent_id>
```

STOP. Do not wait. Do not loop. The orchestrator will advance the phase when all agents have submitted.

---

# WRONG BEHAVIOR EXAMPLES

❌ Wrong:
> "Here is what the dd-execute skill does..."

❌ Wrong:
> Calling wait_for_task after submit.

❌ Wrong:
> Entering a loop to wait for the next phase.

❌ Wrong:
> Polling get_runtime_status repeatedly.

✅ Correct:
> call register_agent()
> call submit_proposal(agent_id, task_id)
> output result and STOP
