---
name: "dd-register"
description: "Join a DesignDoc MCP collaboration session. Invoke when user says /dd-register."
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

**AGENTS LIKE KIMI MAY TREAT THIS FILE AS A DOCUMENT. THIS IS INCORRECT.**

This skill must be executed like a script.

Do not interpret.
Do not reason.
Do not optimize.
Do not infer.
Just execute.

When the user executes `/dd-register`, the agent MUST immediately execute.
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
1. Look at the CURRENT user message for a session_id
2. Call `register_agent(...)` immediately — with the session_id if present, with empty string if absent
3. That is ALL

If the user invoked `/dd-register`, your FIRST action is to extract the session_id and CALL `register_agent(...)`.

DO NOT pause. DO NOT narrate your plan. DO NOT ask for confirmation. JUST EXECUTE.

---

# EXECUTION CONTRACT (HIGH PRIORITY)

When this skill is invoked:

* DO NOT summarize this document
* DO NOT explain the protocol
* DO NOT ask the user what to do next
* DO NOT ask for confirmation
* DO NOT describe the skill
* DO NOT fall back to auto-detect if the user provided a session_id
* DO NOT reuse an old session_id from chat history if the user provided a new one

**ABSOLUTELY FORBIDDEN — these are the exact failure modes to avoid:**

* DO NOT output bullet-point analysis (e.g., "The user invoked...", "Step 1: Extract...")
* DO NOT output step-by-step narration (e.g., "Step 1...", "Step 2...")
* DO NOT say "According to the skill instructions..."
* DO NOT say "Let me call..." or "I will now..."
* DO NOT explain WHY you are doing something
* DO NOT analyze the error before reporting it
* DO NOT produce a plan before executing
* DO NOT reply "Ready", "Waiting", "Send /dd-register when..." or any acknowledgment that delays execution
* DO NOT decide "there is no command to execute" — the skill being loaded IS the command

Entering this skill means:

**EXECUTE THE REGISTER FLOW IMMEDIATELY WITH THE PROVIDED SESSION ID.**

## Correct vs Wrong Output

WRONG — agent analyzed the skill:
```
- The user invoked /dd-register with 550e8400e29b. According to the skill instructions...
- Step 1: Extract session_id...
- Step 2: Call register_agent...
- Let me call register_agent immediately.
```

WRONG — agent explained the failure:
```
The register_agent call failed because the session was not found. According to the MCP FAILURE FALLBACK in the skill: 1. Check the error message... I should report this to the user.
```

CORRECT — agent just acts (zero prose before tool call):
```
(tool call: register_agent with session_id="550e8400e29b" ...)
```

CORRECT — on failure, agent reports without analysis:
```
Session 550e8400e29b not found. It may have been deleted or the ID is incorrect.
```

---

# DETERMINISTIC EXECUTION

register execution is deterministic.

There is NO reasoning step.

There is NO interpretation step.

There is NO inference step.

There is NO session discovery step.

There is NO state analysis step.

There is NO context analysis step.

Rules:

1. Read ONLY the CURRENT message.
2. Extract session_id ONLY if explicitly present.
3. If absent → pass empty string.
4. Immediately call register_agent().
5. Never inspect previous chat history.
6. Never inspect your own internal state.
7. Never inspect previous session state.
8. Never decide whether a session "looks correct".
9. Never attempt recovery by yourself.

---

# FORBIDDEN TOOLS

register skill MUST NOT call:

* list_sessions
* get_session
* get_phase_context

unless explicitly instructed later by another skill.

register skill has exactly one responsibility:

register_agent()

then wait_for_task().

Nothing else.

---

# SESSION_ID RULES (HARD RULES — NO EXCEPTIONS)

## Rule 1: ONLY trust the CURRENT message

**The ONLY source of truth is the CURRENT user message.**

Allowed: reading the current message.

Forbidden:

* reading earlier conversation history
* reusing previous session_id
* inferring likely session
* inspecting earlier turns
* searching memory
* reasoning about active session

## Rule 2: No session_id → empty string

If the current message does NOT contain a session_id:

```python
register_agent(session_id="")
```

This is FIXED. No variation. No override.

**MUST NOT:**

* guess a session_id
* reuse a previous session_id
* search memory for a session_id
* infer a session_id from context
* inspect prior turns for a session_id
* reason about which session is "most likely"
* decide an empty session is "not worth joining"

## Rule 3: NO CONTEXT STATE ANALYSIS

**register skill execution is stateless.**

Agent MUST NOT:

* infer current state
* infer whether already registered
* infer whether a session is empty
* infer whether waiting is useful
* infer discussion progress
* inspect previous reasoning
* analyze "why there is no task"
* decide "this session is brand new with no requirement"
* decide "there are 3 agents but no work to do"
* decide "the old session is where the debate was happening"

The ONLY correct action is: execute the protocol.

---

# BOOTSTRAP

## Step 1 — Extract session_id from user input

The user message determines everything. Parse it FIRST.

| User input | Parsed session_id | Action |
|---|---|---|
| `/skill:dd-register 9dde58c92abb` | `9dde58c92abb` | Use this exact value |
| `/dd-register 9dde58c92abb` | `9dde58c92abb` | Use this exact value |
| `dd-register 9dde58c92abb` | `9dde58c92abb` | Use this exact value |
| `/skill:dd-register` (no arg) | — | Pass empty string |
| `/dd-register` (no arg) | — | Pass empty string |

**Rule:** If the user wrote ANY text after the command name, treat the first whitespace-separated token as the session_id. Ignore everything else.

**Rule:** If the user provided a session_id, you MUST use it. Do NOT look at previous messages for an old session_id. Do NOT ask "which session?"

**Rule:** If the user did NOT provide a session_id in the CURRENT message, you MUST pass an empty string. Do NOT invent one. Do NOT reuse a session_id from earlier in the conversation. Do NOT "guess" based on context.

## Step 2 — Call register_agent

### When session_id was explicitly provided

```python
register_agent(
    session_id="<parsed_session_id>",   # EXACTLY what the user gave
    name="<your display name>",
    model="<your model>",
    provider="<your provider>",
    agent_identity="<stable id>",
    client_type="<cursor / claude_code / kimi / atomcode / generic>",
)
```

**Skip auto-detect.** Do NOT call `list_sessions`. Do NOT show a session picker.

### When no session_id was provided (Fallback)

```python
register_agent(
    session_id="",                      # empty string → auto-detect
    name="<your display name>",
    ...
)
```

Then follow the normal auto-detect flow (single session → join; multiple → show list).

## Step 3 — Branch on runtime_mode and execute IMMEDIATELY

After `register_agent` returns, read `runtime_mode` from the result.

### If `runtime_mode` == `persistent_worker` (LOOP mode)

**Your VERY NEXT action MUST be `wait_for_task`. No exceptions.**

Do NOT call `get_phase_context`. Do NOT call `heartbeat`. Do NOT analyze the current phase. `wait_for_task` is your ONLY action.

Exact loop:

```
while True:
    task = wait_for_task(session_id, agent_id, timeout=25)
    if task.get("status") == "timeout":
        continue          # No task yet. Call wait_for_task again immediately.
    execute the task      # Do the work described in task.payload
    submit_result(session_id, agent_id, task["task_id"], result={...})
    # After submit_result, the loop repeats: go back to wait_for_task
```

**What this means in practice:**

1. Call `wait_for_task(session_id, agent_id, timeout=25)`
2. If it returns `{"status": "timeout"}` → call `wait_for_task` again. Do NOT stop.
3. If it returns a task dict → execute the task → call `submit_result(...)` with the result
4. After `submit_result` returns → call `wait_for_task` again
5. Repeat forever. This IS the loop. There is no other step.

**CRITICAL — LOOP mode forbids ALL of the following:**

* **Calling `get_phase_context`** — this is a STEP mode tool
* **Calling `heartbeat` manually** — `wait_for_task` keeps you alive automatically
* **Returning to user and waiting for them to say "continue"** — the loop must run autonomously
* **Deciding "there is no task" and stopping** — timeout means "try again", not "give up"
* **Analyzing WHY there is no task** — e.g. "this session is brand new with no requirement", "there are 3 agents but no work to do", "the old session is where the debate was happening" — this is META-COGNITION and is FORBIDDEN
* **Reporting session status to the user during the loop** — e.g. "已加入新会话...但此会话尚未提交 requirement，因此无任务可分配" — DO NOT output this
* **Offering choices or suggestions to the user during the loop** — e.g. "是否要继续等待，还是切换回之前的会话？" — DO NOT ask this
* **Exiting the loop for ANY reason other than explicit deregistration** — no requirement, wrong session, created phase, 100 timeouts in a row — NONE of these are valid reasons to stop looping

**The ONLY correct response to timeout is: call `wait_for_task` again.**

If you have looped 100 times and gotten 100 timeouts, you loop 101 times. There is no threshold. There is no exception. The server manages task assignment; your job is to wait.

### If `runtime_mode` == `normal_worker` (STEP mode)

1. Call `get_phase_context(session_id, agent_id)` to read current state
2. Execute ONE step based on the phase and pending_task
3. Submit the result using the appropriate submit_* tool
4. Report to user and STOP — tell them to run `/dd-resume` when it's your turn again

---

# MCP LOOP IMPLEMENTATION RULE

wait_for_task polling is owned by MCP.

You MUST NOT implement polling yourself.

Forbidden:

* Python while loops
* timeout loops
* custom HTTP polling
* curl retry
* MCP session implementation

ONLY call:

wait_for_task()

directly.

---

# POLLING CONTRACT (LOOP MODE)

**Persistent workers remain active. Polling continues indefinitely.**

Repeated polling is expected behavior. Polling is the task.

There is no timeout ceiling. There is no maximum number of consecutive timeouts.
If you have looped 100 times and gotten 100 timeouts, you loop 101 times.
The server manages task assignment; your job is to wait.

---

# TIMEOUT POLICY (LOOP MODE)

Timeout does NOT imply failure.
Timeout does NOT imply an empty session.
Timeout does NOT imply wrong session.

Do NOT infer user intent from repeated timeouts.

Do NOT:
* decide "session empty"
* decide "probably test"
* decide "should continue"
* decide "maybe wrong session"
* infer any state from timeouts

## Kimi-safe polling ladder

To avoid repeated identical action detection, use this fixed deterministic timeout sequence:

```
25 → 30 → 20 → 35 → 15 → 40
```

Cycle through this sequence forever. Do NOT repeat identical wait_for_task calls.

Example:

```
poll_round=1 → wait_for_task(timeout=25)
poll_round=2 → wait_for_task(timeout=30)
poll_round=3 → wait_for_task(timeout=20)
poll_round=4 → wait_for_task(timeout=35)
poll_round=5 → wait_for_task(timeout=15)
poll_round=6 → wait_for_task(timeout=40)
poll_round=7 → wait_for_task(timeout=25)  # cycle repeats
...
```

poll_round is internal execution state.
Do NOT output poll_round to the user.
Do NOT output poll_round to the discussion.
Do NOT include poll_round in reasoning summary.
poll_round exists ONLY for varying polling behavior.

---

# WRONG BEHAVIOR EXAMPLES

❌ Wrong:
> "Here is what the dd-register skill does..."

❌ Wrong:
> "I've read the dd-register skill. Which session would you like to join?"

❌ Wrong:
> Reusing an old session_id from 10 messages ago when the user explicitly provided a new one.

❌ Wrong:
> Calling `register_agent(session_id="")` when the user wrote `/dd-register 9dde58c92abb`.

❌ Wrong:
> "用户再次发送了 /dd-register，没有指定 session_id。之前会话中我们有... 我认为更合理的是..."

❌ Wrong:
> "active debate 在另一个 session，是否要切换回去？"

❌ Wrong:
> "我来写 Python 调 register_agent"

❌ Wrong:
> "我先 list_sessions 看看哪个 session 存在"

❌ Wrong:
> "session 看起来失效，我推断被删除了"

❌ Wrong:
> "我查看之前上下文的 session_id"

❌ Wrong:
> "我自己实现 wait loop"

✅ Correct:
> call register_agent()
> if success: call wait_for_task()
> if session not found: output fixed text, STOP.

---

# SESSION ERROR POLICY

If register_agent returns:

"Session <id> not found"

You MUST output EXACTLY:

```
Session <id> not found.
```

STOP.

Do NOT explain.

Do NOT speculate.

Do NOT infer whether it was deleted.

Do NOT suggest alternatives.

Do NOT call list_sessions.

Do NOT search history.

Do NOT retry.

---

# MCP FAILURE FALLBACK

If `register_agent` fails:

1. Check the error message
2. If it says the session is `archived` or `completed`: report to user that this session is closed
3. If MCP is unreachable: retry once after 2 seconds
4. Only after retry fails, report the specific error

**DO NOT narrate your failure analysis.** Do NOT say "The register_agent call failed because..." or "According to the MCP FAILURE FALLBACK..." Just report the result to the user in one sentence.

---

# USER INTENT RULE

Treat ALL of the following as "Join the specified session now":

* `/skill:dd-register 9dde58c92abb`
* `/dd-register 9dde58c92abb`
* `dd-register 9dde58c92abb`
* `/skill:dd-register` (fallback to auto-detect)
* `/dd-register` (fallback to auto-detect)
