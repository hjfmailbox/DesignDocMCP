---
name: "register"
description: "Join a DesignDoc MCP collaboration session. Invoke when user says /register or wants to join a design discussion."
---

# Register to DesignDoc Session

Join a structured multi-agent design document discussion. No parameters needed — the system auto-detects everything.

**CRITICAL RULES**:
- **Do NOT start the MCP server** — it is already running. You only need to CONNECT to it.
- **Do NOT read or modify the project source code** (`src/`, `server.py`, `engine.py`, etc.) — you are a CLIENT, not a developer of this system.
- **Do NOT implement any logic yourself** — all collaboration logic is handled by the MCP server. Your ONLY job is to CALL the MCP tools listed below.
- **Do NOT try to manually advance phases** — the system advances phases automatically when all agents have submitted. You just need to submit YOUR content for the current phase.
- **Any MCP client can connect** — you do NOT need to be running inside a specific IDE (Cursor, Trae, etc.).

## Step 1: Register

Call the MCP tool `register_agent`. You SHOULD provide your name so other agents can identify you:

- `name`: Your display name (e.g., "Claude Code", "Kimi", "GPT-4"). If omitted, a random name like "Agent-a3f2b1" will be assigned.
- `session_id`: Omit this — the system will auto-detect the active session.

Example: `register_agent(name="Claude Code")`

The system will:

1. **Session**: If only one active session exists, you join it automatically. If multiple exist, you'll get a list to choose from. If none exist, you'll be told to create one via the Web UI.
2. **Your info**: Your name and model are auto-detected. You can optionally specify them if needed.

Save the returned `session_id` and `agent_id` — you need them for all subsequent calls.

## Step 2: Participate

**You do NOT need to implement any loops or timers.** Simply follow this pattern each time you are prompted:

1. Call MCP tool `heartbeat(session_id, agent_id)` — this marks you as active
2. Call MCP tool `get_phase_context(session_id, agent_id)` — this tells you the current phase and what to do
3. Based on the phase, call the appropriate MCP tool to submit your content

That's it. The system handles phase transitions automatically. You just submit content for the current phase when prompted.

**IMPORTANT - Keep your heartbeat alive during wait phases:**
If the current phase is a "wait" phase (e.g., `clarify_review`, `human_review`), you MUST still call `heartbeat(session_id, agent_id)` periodically (every 2-3 minutes) to prevent being marked as inactive. Agents that are inactive for more than 5 minutes will be excluded from the session. When the phase changes, `get_phase_context` will return the new phase so you can take action immediately.

### Phase Actions

| Phase | MCP Tool to Call | Key Parameters |
|-------|-----------------|----------------|
| `clarify_identify` | `submit_assumptions` | `assumptions`: list of `{dimension, assumption, confidence, alternatives: [{label, description}], rationale}`. `dimension` is one of: core_entities, users_and_permissions, data_storage, core_workflow, non_functional, integration_and_boundary. Each MUST include alternatives. Do NOT read other agents' assumptions. |
| `clarify_refine` | `supplement_assumption_options` | `supplements`: list of `{assumption_id, label, description}`. Add missing alternatives to existing assumptions. |
| `clarify_review` | *(wait)* | Wait for human review — do nothing until the phase changes |
| `clarify_rewrite` | `submit_refined_requirement` | `refined_statement` (required), optional: `constraints` (list[str]), `acceptance_criteria` (list[str]) |
| `proposal` | `submit_proposal` | `architecture` (required), optional: `tech_stack`, `tradeoffs`, `risks`, `assumptions`, `unknowns`, `raw_content`. Submit from your assigned perspective. Do NOT read other agents' proposals. |
| `critic` | `submit_challenge` | `target_agent_id`, `target_proposal_id`, `risks` (list[str], min 3), `missing_considerations` (list[str], min 2). Optional: `alternative_proposal`, `category`, `priority`, `confidence`. Vague agreement FORBIDDEN. |
| `revision` | `submit_revision` | `accepted_feedback` (list[str]), `rejected_feedback` (list[str]), `rejection_reasons` (list[str]), `changed_design` (str). Must show concrete design changes. |
| `optimization` | `submit_optimization` | `description` (required). Optional: `impact`, `tradeoff`, `complexity_change`. |
| `devils_advocate` | `submit_devils_advocate` | `failure_modes` (list[str]). Optional: `mitigation`, `risk_score` (0.0-1.0). If designated, argue the design will fail. |
| `consensus` | `cast_consensus_vote` | `vote_type`: agree / disagree / abstain / needs_clarification. Optional: `comment`. |
| `human_review` | *(wait)* | Wait for human decision — do nothing until the phase changes |

## Rules

1. Never skip a phase — submit content for every phase
2. No anchoring bias — do NOT read other agents' proposals in PROPOSAL phase
3. No polite agreement — vague agreement in CRITIC phase is FORBIDDEN
4. Always include alternatives — every assumption in CLARIFY_IDENTIFY must have alternatives
5. Respect your perspective — argue from your assigned perspective in PROPOSAL phase
6. Do NOT start the MCP server — it is already running, just connect and call tools
7. Do NOT read or modify the project source code — you are a CLIENT of the MCP server, not its developer
8. Do NOT try to manually advance phases — the system does this automatically when all agents submit
