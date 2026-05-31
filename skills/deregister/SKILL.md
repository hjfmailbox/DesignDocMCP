---
name: "deregister"
description: "Leave a DesignDoc MCP collaboration session. Invoke when user says /deregister or wants to leave a design discussion."
---

# Deregister from DesignDoc Session

Leave the current collaboration session.

## How It Works

1. Call `deregister_agent(session_id, agent_id)` to mark yourself as inactive
2. Stop the auto-participation loop (wait_for_task / submit_result)
3. Inform the user you have left the session

## After Deregistration

- You will be marked as inactive (`is_active = false`)
- You will no longer be counted for phase completion checks
- The session will continue with remaining active agents
- If you are the last active agent, the session may require human intervention

## Rejoin

If you want to rejoin later, simply call `/register` again with the same `agent_identity`.
The system will automatically restore your previous participation state.
