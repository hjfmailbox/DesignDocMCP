package orchestrator

import (
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"

	"github.com/fluorine/designdoc-mcp/probe/internal/state"
)

// CLISpawner invokes real agent processes (Claude Code or Cursor CLI)
// using the OS exec facility.  Each Spawn fires a detached process that
// executes the dd-execute skill once and then exits.
type CLISpawner struct {
	// WorkDir is the base directory where agent processes run.
	// If empty, uses the current working directory.
	WorkDir string
}

func (c *CLISpawner) Spawn(sessionID, agentID, phase, taskID string) error {
	sess := state.GetSessionByAgentID(agentID)
	if sess == nil {
		return fmt.Errorf("session not found for agent %s", agentID)
	}
	agent := sess.GetAgent(agentID)
	if agent == nil {
		return fmt.Errorf("agent %s not found in session", agentID)
	}

	prompt := fmt.Sprintf("/dd-execute %s %s", phase, taskID)

	var cmd *exec.Cmd
	switch strings.ToLower(agent.Client) {
	case "claude", "claude-code":
		cmd = exec.Command("claude", "-p", prompt)
	case "cursor":
		if runtime.GOOS == "windows" {
			// agent.ps1 is a PowerShell script; invoke it via powershell.
			cmd = exec.Command("powershell", "-Command",
				fmt.Sprintf("agent -p '%s' --yolo", prompt))
		} else {
			cmd = exec.Command("agent", "-p", prompt, "--yolo")
		}
	default:
		return fmt.Errorf("unknown agent client %q for agent %s", agent.Client, agentID)
	}

	if c.WorkDir != "" {
		cmd.Dir = c.WorkDir
	}

	// Detach from parent so the orchestrator doesn't wait for the agent.
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start agent %s: %w", agentID, err)
	}

	// Intentionally do NOT call cmd.Wait().  The agent is a one-shot
	// process; it runs, submits, and exits on its own.  The orchestrator
	// observes the barrier, not the process lifetime.
	return nil
}
