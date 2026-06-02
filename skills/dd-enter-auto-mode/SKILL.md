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
5. Handle initial submit if needed
6. Enter push-based event loop until session ends
7. That is ALL

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

# STEP 2 — Set logging level (OPTIONAL)

If the client supports `logging/setLevel`, call it immediately after register_agent returns.

```python
logging/setLevel(level="info")
```

Some MCP clients (e.g. Claude Code) do not expose this tool. If the tool is not available, proceed to Step 3. Push notifications may still work via the client's LoggingMessageHandler.

---

# STEP 3 — Query initial status

Call `get_runtime_status` with the `agent_id` returned from Step 1.

```python
get_runtime_status(
    agent_id="<agent_id>",
)
```

Read the result.

---

# STEP 4 — Handle initial state

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

## Case C: Waiting (REGISTERED or no task yet)

If `phase` == `REGISTERED` or `needs_submit` == `false`:

Proceed to push loop.

---

# STEP 5 — Push-based event loop

This skill is **pure push-based**. The agent waits for server push notifications via the `LoggingMessageHandler` callback. No polling. No periodic `get_runtime_status` calls.

## Push handler setup

Configure your `LoggingMessageHandler` to parse each push and trigger the appropriate submit.

```python
on_push_received(data):
    payload = json_parse(data)
    phase        = payload["phase"]
    task_id      = payload["task_id"]
    action       = payload["required_action"]   # e.g. "submit_proposal"

    # Map required_action to submit tool
    tool_map = {
        "submit_proposal":  submit_proposal,
        "submit_challenge": submit_challenge,
        "submit_revision":  submit_revision,
        "submit_consensus": submit_consensus,
    }
    submit_tool = tool_map[action]

    # Call the submit tool
    submit_tool(
        agent_id="<agent_id>",
        task_id=task_id,
        content={},
    )

    # After submit, check if session has ended
    status = get_runtime_status(agent_id="<agent_id>")
    if status.phase in ["COMPLETE", "FAILED_TIMEOUT"]:
        output_final_result(status)
        STOP
```

## Main thread behavior

The main thread does NOTHING after Step 4 except wait. All subsequent actions are triggered by push notifications.

```python
# After Step 4, main thread simply waits.
# Each push triggers: submit -> get_runtime_status -> check if done.
# If no push arrives, the agent waits indefinitely.
wait_forever()
```

## Push reliability note

If your MCP client (Kimi, Cursor) does not reliably deliver logging pushes, this skill will appear to hang. That is a client/SDK limitation, not a server issue.

In that case, the user must either:
- Use a client that supports MCP logging notifications (Claude Code, Trae), OR
- Invoke a polling-based skill instead.

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
> Polling `get_runtime_status` on a timer.

❌ Wrong:
> Implementing a custom HTTP client instead of calling MCP tools.

✅ Correct:
> call register_agent()
> call logging/setLevel(info)
> call get_runtime_status(agent_id)
> if needs_submit: call submit_proposal(...)
> wait for push -> submit -> check done
