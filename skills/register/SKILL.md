---
name: "register"
description: "Join a DesignDoc MCP collaboration session. Invoke when user says /register or wants to join a design discussion."
---

# DesignDoc Register Protocol

You are joining a workflow-driven MCP debate system. This is NOT a chat. After
`/register` you become a debate worker driven by the MCP Server.

How you participate depends on **whether your client can sustain a long
autonomous loop**. The server detects this for you and returns a `runtime_mode`.
There are exactly two modes:

| runtime_mode | meaning | how you run |
|---|---|---|
| `persistent_worker` | LOOP mode — client can run long without disconnecting | `wait_for_task` loop (Section 3) |
| `normal_worker` | STEP mode — client cannot stay alive long | one step, then hand back to user (Section 4) |

> ⚠️ Do NOT guess your mode. Read it from the `register_agent` response.

---

# 0. Why two modes (read this once)

An LLM agent only "thinks" while it is invoked; the MCP Server has **no way to
push and wake a sleeping agent**. So "keep participating" really means "keep the
current turn alive". Clients differ wildly in how long a turn / a single tool
call may run:

* Some clients sustain many consecutive tool calls and long blocking calls with
  no confirmation → they can run the LOOP.
* Others cap turn length, cap tool-call count, hard-cap a single call's
  duration, or require confirmation → the LOOP would silently die on them, so
  they must run in STEP mode and be re-invoked by the user via `/resume`.

You MUST NOT fake a loop on a client that cannot sustain one. Faking it (e.g.
pretending to wait, or claiming "I'll keep running" then stopping) is forbidden.

---

# 1. Capability detection (who runs which mode)

Detection is done **server-side** from your `client_type`. Pass it when you
register so detection is accurate.

**Known LOOP-capable clients** (verified by stress test — sustain long blocking
+ many consecutive calls + no confirmation):

| client_type | client | verified ceiling |
|---|---|---|
| `cursor` | Cursor (CLI / Composer Agent) | single block ≥420s; no count/turn cap |
| `claude_code` | Claude Code | single block ≥420s; no count/turn cap |
| `kimi` | Kimi CLI | single call hard-capped **300s**; no count/turn cap |
| `atomcode` | AtomCode | single call hard-capped **300s**; no count/turn cap |

**Everything else → STEP mode.** Empty, `generic`, `trae`, or any client not in
the table above defaults to `normal_worker`. This is the safe default: we never
assume an unverified client can hold a loop.

> If your client is not in the table and you believe it CAN sustain a long loop,
> do not self-promote. Run STEP mode, and tell the user it can be added to the
> known-capable list after running the capability stress test.

---

# 2. Bootstrap (ALL modes)

On `/register`, immediately:

1. Call `register_agent(...)`. Pass what you know about yourself:
   ```
   register_agent(
       session_id="",                 # omit → auto-detect single session
       name="<your display name>",    # e.g. "Cursor Composer Agent"
       model="<your model>",          # optional
       provider="<your provider>",    # optional
       agent_identity="<stable id>",  # SAME string across reconnects → auto-rejoin
       client_type="<see table §1>",  # cursor / claude_code / kimi / atomcode / generic
   )
   ```
   `agent_identity` MUST be stable across reconnects (e.g.
   `cursor_cli_<machine>_<hash>`) so disconnects auto-rejoin instead of creating
   duplicates.
2. Persist `session_id`, `agent_id`, and the returned `runtime_mode`.
3. The response already ran one `heartbeat` + `get_phase_context` for you; read
   `phase_context` and `pending_task`.
4. Branch on `runtime_mode`:
   * `persistent_worker` → go to **Section 3 (LOOP)**.
   * `normal_worker` → go to **Section 4 (STEP)**.

If `register_agent` returns `{"action": "choose_session"}`, show the list and
ask the user which to join. If `{"action": "error"}` (no active session), tell
the user to create one in the Web UI (http://localhost:8765) and stop.

---

# 3. LOOP mode (`persistent_worker`)

Run the autonomous worker loop. Do NOT return to the user, do NOT ask for
confirmation, do NOT stop after one task.

```python
while session_active:
    task = wait_for_task(session_id, agent_id, timeout=25)
    #                                          ^^^^^^^^^^
    # 25s short long-poll. 建议范围 20~60s。务必 < 最低客户端单次调用上限(300s)。
    # 实时性要求低可调大以减少请求；要更稳就保持 25s。服务器默认值见 constants.py。

    if task.get("status") == "timeout":
        continue                      # no work yet — just poll again

    result = process(task)            # build the structured artifact for task_type
    submit_result(session_id, agent_id, task["task_id"], result)
    # result MUST include "_task_type" matching task["task_type"]; structured data only.
```

Rules:
* Use **short polling** (`timeout=25`), NOT a single long block. This stays
  safely under every known client's single-call ceiling (incl. the 300s hard
  caps) and avoids silent kills.
* Continue until: session archived / explicit `/deregister` / fatal error.
* On unexpected stop, recover by calling `register_agent(...)` again with the
  same `agent_identity` (auto-rejoin), then resume the loop.
* Output is structured (YAML / JSON-compatible). No chat prose in submissions.

---

# 4. STEP mode (`normal_worker`)

Your client cannot hold a loop, so do **exactly one step per invocation**, then
hand control back to the user. Do not block, do not fake a loop.

One step:

1. `heartbeat(session_id, agent_id)`
2. `get_phase_context(session_id, agent_id)` → read `current_phase`
3. Submit the artifact for the current phase using the matching tool
   (see Section 6 phase table). If the phase is a wait phase
   (`clarify_review` / `human_review`) or you have already submitted this phase,
   submit nothing.
4. STOP and report to the user, plainly:
   * what phase you are in and what you just submitted (or "nothing to do yet");
   * that the flow advances only when all participants submit;
   * **"When the Web UI marks me ⏳ needs-wake (or the phase advances), run
     `/resume` to continue."**

Do NOT pretend to keep running. Do NOT poll in a loop. Each `/resume` performs
one more step (the `/resume` skill).

> Optional acceleration: a STEP-mode client may be pumped automatically by the
> client's own scheduler (e.g. Cursor `/loop`, Claude Code hooks/cron) to run
> `/resume` on an interval. Manual `/resume` is the universal baseline.

---

# 5. Auto-rejoin & recovery

`/register` is idempotent. With a stable `agent_identity`:

```python
if existing_identity_matches:
    restore_previous_worker()   # keeps perspective, no duplicate agent
else:
    create_worker()
```

Disconnects are normal. Re-running `/register` (or `/resume` in STEP mode)
recovers automatically. There is no separate `/rejoin`.

---

# 6. Phase → action map

| Phase | Action (tool) |
|-------|---------------|
| `clarify_identify` | `submit_assumptions` (independent, no peeking) |
| `clarify_refine` | `supplement_assumption_options` |
| `clarify_review` | wait for human |
| `clarify_rewrite` | `submit_refined_requirement` |
| `proposal` | `submit_proposal` (assigned perspective, no peeking) |
| `critic` | `submit_challenge` (3+ risks, 2+ missing, no polite agreement) |
| `revision` | `submit_revision` (must show changes) |
| `optimization` | `submit_optimization` |
| `devils_advocate` | `submit_devils_advocate` (if designated) |
| `consensus` | `cast_consensus_vote` |
| `human_review` | wait for human |

In LOOP mode these are driven via `wait_for_task` task_type + `submit_result`
(with `_task_type`). In STEP mode call the phase tool directly after
`get_phase_context`.

---

# 7. Forbidden

* Faking a loop / claiming to keep running then stopping (STEP mode).
* Using a single long blocking `wait_for_task` (e.g. timeout=300) — short-poll.
* Self-promoting an unverified client to LOOP mode.
* Writing a background script/process to "stay alive" — it gets killed on turn
  end and cannot drive the debate.
* Asking the user for confirmation between steps, reinterpreting workflow,
  manually advancing phases, or coordinating directly with other agents.
* Conversational prose in submissions — structured data only.

---

# 8. Runtime bias

When a task carries `runtime_bias`, prioritize it. Possible values:
`security_privacy`, `scalability`, `cost_efficiency`, `operational_stability`,
`developer_experience`, `user_experience`, `maintainability`,
`integration_ecosystem`, `data_integrity`, `performance_efficiency`.
