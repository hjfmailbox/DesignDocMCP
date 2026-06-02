---
name: "dd-enter-auto-mode"
description: "Enter persistent automatic MCP-driven workflow handling for MiniDebateRuntime. Invoke when user says /dd-enter-auto-mode."
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

If you think "I could implement this myself" — DO NOT.

This skill is execution-only.

---

# THIS SKILL IS EXECUTABLE, NOT EXPLANATORY

**AGENTS MAY TREAT THIS FILE AS A DOCUMENT. THIS IS INCORRECT.**

This skill must be executed like a script.

Do not interpret.
Do not reason.
Do not optimize.
Do not infer.
Just execute.

When the user executes `/dd-enter-auto-mode`, the agent MUST immediately execute.
The agent MUST NOT:

* summarize this skill
* explain the protocol
* ask clarifying questions
* reason about likely intent
* pause for confirmation
* analyze context before acting

---

# ZERO-THOUGHT EXECUTION DIRECTIVE

**YOU ARE IN EXECUTION MODE. YOU ARE NOT IN DOCUMENTATION-READING MODE.**

If you are reading this skill right now, it means the skill HAS ALREADY BEEN INVOKED. Do NOT analyze why you see this text. Do NOT treat this as the user "sending the skill definition." Do NOT respond with "Ready" or "Waiting for command."

Your ONLY job is:
1. Detect your client environment
2. Call `register_agent`
3. Call `logging/setLevel`
4. Call `get_runtime_status`
5. Enter the polling loop until the session is COMPLETE or FAILED_TIMEOUT
6. That is ALL

If the user invoked `/dd-enter-auto-mode`, your FIRST action is to detect client environment, then call `register_agent`.

DO NOT pause. DO NOT narrate your plan. DO NOT ask for confirmation. JUST EXECUTE.

---

# EXECUTION CONTRACT (HIGH PRIORITY)

When this skill is invoked:

* DO NOT summarize this document
* DO NOT explain the protocol
* DO NOT ask the user what to do next
* DO NOT ask for confirmation
* DO NOT describe the skill
* DO NOT fall back to auto-detect

**ABSOLUTELY FORBIDDEN:**

* DO NOT output bullet-point analysis
* DO NOT output step-by-step narration
* DO NOT say "According to the skill instructions..."
* DO NOT say "Let me call..." or "I will now..."
* DO NOT explain WHY you are doing something
* DO NOT analyze the error before reporting it
* DO NOT produce a plan before executing
* DO NOT reply "Ready", "Waiting", or any acknowledgment that delays execution

---

# SERVER TARGET

**ONLY use the MCP server currently connected by the user.**

This skill targets `MiniDebateRuntime` at `http://127.0.0.1:8799/mcp`.

Do NOT connect to DesignDocMCP main server.

Do NOT infer which server to use.

---

# STATELESS EXECUTION

This skill execution is stateless.

Agent MUST NOT:

* infer current state
* infer whether already registered
* inspect previous chat history for session_id or agent_id
* analyze "why there is no task"
* decide "this session is brand new"
* decide "probably test"

The ONLY correct action is: execute the protocol.

---

# STEP 0 — Detect client environment

Before calling any tool, determine your current runtime environment.

**How to detect:**

Read your system prompt or execution context. Look for identifiers that reveal which MCP client is hosting you.

| If your context contains | Then client = |
|---|---|
| "Claude Code" or "claude-code" | `claude-code` |
| "Cursor" or "cursor" | `cursor` |
| "Trae" or "trae" | `trae` |
| "Kimi" or "kimi" (native, not inside another client) | `kimi` |
| None of the above | Use the model provider name (e.g. `openai`, `anthropic`) |

**Rules:**

* `client` is the **MCP client application** (Claude Code, Cursor, Trae), NOT the LLM model name.
* `model` is the **LLM model name** (kimi-k2.6, gpt-4, claude-sonnet).
* If you are Kimi running inside Claude Code: `client="claude-code"`, `model="kimi-k2.6"`.
* If you are Claude running inside Claude Code: `client="claude-code"`, `model="claude-sonnet"`.
* Do NOT ask the user. Do NOT output your detection reasoning. Just use the detected value.

---

# STEP 1 — Register (idempotent with retry)

Call `register_agent` with your detected identity.

**Retry policy (exponential backoff):**

| Attempt | Delay | Total wait |
|---|---|---|
| 1 | immediate | 0s |
| 2 | 3 seconds | 3s |
| 3 | 6 seconds | 9s |
| Max | — | 3 attempts total |

```python
for attempt in 1..3:
    result = register_agent(
        client="<detected-client-name>",
        model="<your-model-name>",
    )
    if result.success:
        break
    if attempt < 3:
        wait(attempt * 3)   # 3s, then 6s
```

**If all 3 attempts fail:**

Output EXACTLY:
```
Register failed after 3 attempts.
```
STOP.

**Retry rules:**

* DO NOT output intermediate failure messages (e.g. "Attempt 1 failed...").
* DO NOT analyze why register failed.
* DO NOT ask the user what to do.
* DO NOT switch to a different tool.
* Just wait silently and retry.

This is IDEMPOTENT. If an active session already exists for this exact client+model combination, the existing session is returned. No duplicate session is created. No duplicate phase loop is launched.

**NEVER skip this step.** Even if you believe you are already registered, call it. The server handles idempotency.

---

# STEP 2 — Set logging level (CRITICAL)

Call `logging/setLevel` immediately after register_agent returns.

```python
logging/setLevel(level="info")
```

**Without this step, server push notifications are silently dropped by the MCP SDK.** The server will think pushes succeeded, but the client receives nothing.

This is a known issue with Go SDK v1.6.1. Do NOT skip this step.

---

# STEP 3 — Query runtime status

Call `get_runtime_status` with the `agent_id` returned from Step 1.

```python
get_runtime_status(
    agent_id="<agent_id>",
)
```

Read the result.

---

# STEP 4 — Branch on status

## Case A: Session already complete or failed

If `phase` == `COMPLETE` or `phase` == `FAILED_TIMEOUT`:

Output EXACTLY:
```
Session <session_id>: <phase>
```
STOP.

## Case B: Needs immediate submit

If `needs_submit` == `true`:

Call the appropriate submit tool based on `phase`:

| Phase | Tool | Arguments |
|---|---|---|
| PROPOSAL | `submit_proposal` | agent_id, task_id, content={} |
| CHALLENGE | `submit_challenge` | agent_id, task_id, content={} |
| REVISION | `submit_revision` | agent_id, task_id, content={} |
| CONSENSUS | `submit_consensus` | agent_id, task_id, content={} |

Content may be empty object `{}` or minimal payload.

After submit returns, proceed to polling loop.

## Case C: Waiting for phase

If `phase` == `REGISTERED` or `needs_submit` == `false`:

Proceed directly to polling loop.

---

# STEP 5 — Polling loop

**Push notifications are UNRELIABLE.** Some clients (Kimi, Cursor) do not receive MCP logging notifications even with correct level set. Therefore polling is the PRIMARY mechanism. Push is secondary.

Use this deterministic timeout sequence, cycling forever:

```
25 → 30 → 20 → 35 → 15 → 40
```

Round 1: wait 25s
Round 2: wait 30s
Round 3: wait 20s
Round 4: wait 35s
Round 5: wait 15s
Round 6: wait 40s
Round 7: wait 25s (cycle repeats)
...

**Loop body:**

1. Call `get_runtime_status(agent_id=...)`
2. If `phase` == `COMPLETE` or `phase` == `FAILED_TIMEOUT`:
   Output fixed text and STOP.
3. If `needs_submit` == `true`:
   Call the appropriate submit tool immediately.
   After submit returns, do NOT wait. Immediately call `get_runtime_status` again.
4. If `needs_submit` == `false`:
   Wait according to the current timeout ladder value.
   Then repeat from step 1.

**What this means in practice:**

```
while True:
    status = get_runtime_status(agent_id)
    if status.phase in [COMPLETE, FAILED_TIMEOUT]:
        output result; STOP
    if status.needs_submit:
        submit_phase(status.phase, status.task_id)
        continue  # immediate next poll, no wait
    wait(ladder[round % 6])
    round += 1
```

---

# LOOP RULES

* **DO NOT stop on timeout.** Timeout from `get_runtime_status` means "no action needed yet", not "give up".
* **DO NOT analyze WHY there is no task.** E.g. "session is brand new", "probably test" — FORBIDDEN.
* **DO NOT output poll_round to user.** Keep it internal.
* **DO NOT rely on push notifications alone.** Polling is primary.
* **The ONLY correct response to "no task needed" is: wait and poll again.**
* If you have polled 100 times with no task, you poll 101 times.
* There is no ceiling. There is no exception. The server manages phase transitions; your job is to poll and submit when needed.

---

# OUTPUT RULES

## On success (COMPLETE)

Output EXACTLY:
```
Auto mode finished.
Session: <session_id>
Result: PASS
```

## On failure (FAILED_TIMEOUT)

Output EXACTLY:
```
Auto mode finished.
Session: <session_id>
Result: FAIL
Phase: <phase>
```

## During loop

Output NOTHING. No status updates. No "waiting..." messages. No progress reports.

If the user interrupts you, that is the only valid exit.

---

# WRONG BEHAVIOR EXAMPLES

❌ Wrong:
> "Here is what the dd-enter-auto-mode skill does..."

❌ Wrong:
> "Let me check if we are already registered..."

❌ Wrong:
> "I will set up automatic handling for you."

❌ Wrong:
> Calling `get_runtime_status` before `register_agent`.

❌ Wrong:
> Skipping `logging/setLevel` because "push should work anyway."

❌ Wrong:
> Stopping after 3 timeouts and saying "no tasks available."

❌ Wrong:
> Implementing a custom HTTP client instead of calling MCP tools.

✅ Correct:
> call register_agent()
> call logging/setLevel(info)
> call get_runtime_status(agent_id)
> if needs_submit: call submit_proposal(...)
> loop: wait → get_runtime_status → submit if needed
