---
name: "dd-register"
description: "Join a specific DesignDoc MCP collaboration session by ID. Invoke when user says /dd-register <session_id> or wants to join a specific session."
---

# ZERO-THOUGHT EXECUTION DIRECTIVE

**YOU ARE IN EXECUTION MODE. YOU ARE NOT IN DOCUMENTATION-READING MODE.**

If you are reading this skill right now, it means the skill HAS ALREADY BEEN INVOKED. Do NOT analyze why you see this text. Do NOT treat this as the user "sending the skill definition." Do NOT respond with "Ready" or "Waiting for command."

Your ONLY job is:
1. Look at the CURRENT user message for a session_id
2. Call `register_agent(...)` immediately — with the session_id if present, with empty string if absent
3. That is ALL

If the user invoked `/skill:dd-register` (or `/dd-register`), your FIRST action is to extract the session_id and CALL `register_agent(...)`.

DO NOT pause. DO NOT narrate your plan. DO NOT ask for confirmation. JUST EXECUTE.

---

# DesignDoc Direct Session Register

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

# BOOTSTRAP

## Step 1 — Extract session_id from user input

The user message determines everything. Parse it FIRST.

| User input | Parsed session_id | Action |
|---|---|---|
| `/skill:dd-register 9dde58c92abb` | `9dde58c92abb` | Use this exact value |
| `/dd-register 9dde58c92abb` | `9dde58c92abb` | Use this exact value |
| `dd-register 9dde58c92abb` | `9dde58c92abb` | Use this exact value |
| `/skill:dd-register` (no arg) | — | Fall back to auto-detect (see Fallback) |
| `/dd-register` (no arg) | — | Fall back to auto-detect (see Fallback) |

**Rule:** If the user wrote ANY text after the command name, treat the first whitespace-separated token as the session_id. Ignore everything else.

**Rule:** If the user provided a session_id, you MUST use it. Do NOT look at previous messages for an old session_id. Do NOT ask "which session?"

**Rule:** If the user did NOT provide a session_id in the CURRENT message, you MUST pass an empty string (or omit session_id). Do NOT invent one. Do NOT reuse a session_id from earlier in the conversation. Do NOT "guess" based on context.

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
    session_id="",                      # omit → auto-detect
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

# WRONG BEHAVIOR EXAMPLES

❌ Wrong:
> "Here is what the dd-register skill does..."

❌ Wrong:
> "I've read the dd-register skill. Which session would you like to join?"

❌ Wrong:
> Reusing an old session_id from 10 messages ago when the user explicitly provided a new one.

❌ Wrong:
> Calling `register_agent(session_id="")` when the user wrote `/dd-register 9dde58c92abb`.

✅ Correct:
> Parse `9dde58c92abb` from user input, then immediately call `register_agent(session_id="9dde58c92abb", ...)`

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

---

# REUSE WARNING

Some agents (e.g. Kimi) tend to reuse variables from earlier in the conversation.

**When this skill is invoked, the user's CURRENT message overrides ALL historical context.**

If the current message contains a session_id, use it. If not, then and ONLY then check if a previous turn already established a session_id.
