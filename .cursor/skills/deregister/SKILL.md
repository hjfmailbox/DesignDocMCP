---
name: "deregister"
description: "Leave a DesignDoc MCP collaboration session. Invoke when user says /deregister or wants to leave a design discussion."
---

# Deregister from DesignDoc Session

Leave the current collaboration session. No parameters needed.

## How It Works

1. Send a final `heartbeat(session_id, agent_id)` to mark your last active time
2. Stop the auto-participation loop (heartbeat + phase monitoring)
3. Inform the user you have left the session

The session will continue with remaining agents. If you are the last active agent, the session may require human intervention.
