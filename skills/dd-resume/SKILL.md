---
name: "dd-resume"
description: "Advance one step in a DesignDoc MCP session (STEP-mode clients). Invoke when user says /dd-resume or the Web UI marks you as needing a manual wake."
---

# DesignDoc Resume (STEP-mode pump)

`/dd-resume` performs **exactly one collaboration step** and then hands control
back to the user. It is the manual "pump" for clients that cannot hold a long
autonomous loop (those registered as `normal_worker` / STEP mode by `/dd-register`).

> If you registered as `persistent_worker` (LOOP mode), you do NOT need
> `/dd-resume` — your `wait_for_task` loop already drives itself. `/dd-resume` is only
> for STEP mode.

---

# Preconditions

You must already be registered (have `session_id` + `agent_id`). If you don't,
run `/dd-register` first. If your identity was lost on disconnect, re-run
`/dd-register` with the same `agent_identity` to auto-rejoin, then `/dd-resume`.

---

# One step (do this, then STOP)

1. `heartbeat(session_id, agent_id)` — stay marked active.
2. `get_phase_context(session_id, agent_id)` — read `current_phase`.
3. Act on the phase:
   * If it's a wait phase (`clarify_review` / `human_review`), or you have
     already submitted for this phase → submit nothing.
   * Otherwise submit the artifact for the current phase using the matching
     tool:

   | Phase | Tool |
   |-------|------|
   | `clarify_identify` | `submit_assumptions` |
   | `clarify_refine` | `supplement_assumption_options` |
   | `clarify_rewrite` | `submit_refined_requirement` |
   | `proposal` | `submit_proposal` |
   | `critic` | `submit_challenge` |
   | `revision` | `submit_revision` |
   | `optimization` | `submit_optimization` |
   | `devils_advocate` | `submit_devils_advocate` |
   | `consensus` | `cast_consensus_vote` |

   Submissions are structured data (no chat prose). Respect any assigned
   `runtime_bias` and the phase rules (e.g. critic: 3+ risks, no polite
   agreement; proposal: stay on your perspective, no peeking).
4. **STOP** and report plainly:
   * phase + what you submitted (or "nothing to do — waiting on others/human");
   * that the flow advances only when all participants submit;
   * **"Run `/dd-resume` again when the Web UI marks me ⏳ needs-wake or the phase
     advances."**

---

# Forbidden

* Do NOT loop, poll, or call `wait_for_task` in STEP mode.
* Do NOT fake "staying alive" or claim you will keep running.
* Do NOT submit twice for the same phase, manually advance phases, or
  coordinate directly with other agents.
* Do NOT write a background script/process to keep running.

One `/dd-resume` = one step. The user (or the client's own scheduler, e.g. Cursor
`/loop`) re-invokes `/dd-resume` when it's your turn again.
