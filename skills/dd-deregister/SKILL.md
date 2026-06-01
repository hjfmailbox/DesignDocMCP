---
name: "dd-deregister"
description: "Leave a DesignDoc MCP collaboration session. Invoke when user says /dd-deregister or wants to leave a design discussion."
---

# ZERO-THOUGHT EXECUTION DIRECTIVE

**YOU ARE IN EXECUTION MODE. YOU ARE NOT IN DOCUMENTATION-READING MODE.**

If you are reading this skill right now, it means the skill HAS ALREADY BEEN INVOKED. Do NOT analyze why you see this text. Do NOT treat this as the user "sending the skill definition." Do NOT respond with "Ready" or "Waiting for command."

Your ONLY job is:
1. Call `deregister_agent(session_id, agent_id)` immediately
2. That is ALL

DO NOT pause. DO NOT narrate your plan. DO NOT ask for confirmation. JUST EXECUTE.

---

# DesignDoc Deregister

# EXECUTION CONTRACT (HIGH PRIORITY)

When this skill is invoked:

* DO NOT summarize this document
* DO NOT explain the protocol
* DO NOT ask the user what to do next
* DO NOT ask for confirmation
* DO NOT describe the skill
* DO NOT analyze why the user wants to leave

**ABSOLUTELY FORBIDDEN — these are the exact failure modes to avoid:**

* DO NOT output bullet-point analysis (e.g., "The user wants to leave...", "Step 1:...")
* DO NOT output step-by-step narration
* DO NOT say "According to the skill instructions..."
* DO NOT say "Let me call..." or "I will now..."
* DO NOT explain WHY you are doing something
* DO NOT produce a plan before executing
* DO NOT reply "Ready", "Waiting", or any acknowledgment that delays execution

---

## Correct vs Wrong Output

WRONG — agent analyzed the skill:
```
- The user wants to leave the session. According to the skill...
- Step 1: Call deregister_agent...
- Step 2: Inform the user...
```

WRONG — agent asked for confirmation:
```
Are you sure you want to leave the session?
```

CORRECT — agent just acts (zero prose before tool call):
```
(tool call: deregister_agent with session_id="...", agent_id="...")
```

---

# BOOTSTRAP

## Step 1 — Call deregister_agent

Use the `session_id` and `agent_id` you are currently registered with.

```python
deregister_agent(
    session_id="<your_current_session_id>",
    agent_id="<your_current_agent_id>",
)
```

**No confirmation.** Do NOT ask "are you sure?" Do NOT explain the consequences.

## Step 2 — Stop participating

- LOOP mode (`persistent_worker`): break out of the `wait_for_task` loop immediately
- STEP mode (`normal_worker`): do not run `/dd-resume` again

## Step 3 — Report result

One sentence only. Examples:

- Success: "Left session 9dde58c92abb."
- Failure: "Failed to leave session: <error message>"

DO NOT explain what deregistration means. DO NOT list the after-effects.

---

# MCP FAILURE FALLBACK

If `deregister_agent` fails:

1. Check the error message
2. If MCP is unreachable: retry once after 2 seconds
3. Only after retry fails, report the specific error in one sentence

**DO NOT narrate your failure analysis.**

---

# USER INTENT RULE

Treat ALL of the following as "Leave the session now":

* `/skill:dd-deregister`
* `/dd-deregister`
* `dd-deregister`
* "I want to leave"
* "Exit session"
* "Stop participating"
