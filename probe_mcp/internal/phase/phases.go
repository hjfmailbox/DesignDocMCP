package phase

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/fluorine/designdoc-mcp/probe/internal/logger"
	"github.com/fluorine/designdoc-mcp/probe/internal/state"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

const phasePushTimeout = 30 * time.Second

var actionMap = map[string]string{
	state.PhaseProposal:  "submit_proposal",
	state.PhaseChallenge: "submit_challenge",
	state.PhaseRevision:  "submit_revision",
	state.PhaseConsensus: "submit_consensus",
}

// EnterPhase creates tasks for every active agent in the session.
// For challenge phase, tasks include a fixed topology target.
func EnterPhase(session *state.MultiAgentSession, phase string) {
	session.ClearTasks()
	session.SetPhase(phase)

	agents := session.GetAgents()
	for _, agent := range agents {
		if agent.GetStatus() != "active" {
			continue
		}

		taskID := "task_" + state.RandomHex(6)
		task := &state.PhaseTask{
			TaskID:  taskID,
			Phase:   phase,
			AgentID: agent.AgentID,
		}

		if phase == state.PhaseChallenge {
			task.TargetID = session.GetChallengeTarget(agent.AgentID)
		}

		session.AddTask(task)
		logger.LogTimeline(session.SessionID, "task_created", phase, taskID)
	}

	logger.LogTimeline(session.SessionID, "phase_started", phase, "")
}

// PushTask sends an MCP logging push to the agent's ServerSession.
// Returns true if the push was attempted (regardless of transport error).
func PushTask(task *state.PhaseTask, agent *state.Agent) bool {
	ss := agent.GetServerSession()
	if ss == nil {
		return false
	}

	payload := map[string]any{
		"phase":           task.Phase,
		"task_id":         task.TaskID,
		"required_action": actionMap[task.Phase],
		"retry":           task.PushCount,
	}
	if task.TargetID != "" {
		payload["target_agent"] = task.TargetID
	}

	data, _ := json.Marshal(payload)

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	sessionID := sessionByTask(task)

	logger.LogNotificationSent(sessionID, agent.AgentID, agent.DisplayName, task.Phase, task.TaskID, "logging/message", payload)

	err := ss.Log(ctx, &mcp.LoggingMessageParams{
		Level:  mcp.LoggingLevel("info"),
		Data:   string(data),
		Logger: "MiniDebateRuntime",
	})

	task.IncrementPush()
	logger.LogPush(sessionID, task.Phase, task.TaskID, task.PushCount)

	if err != nil {
		logger.LogTimeline(sessionID, "push_failed", task.Phase, task.TaskID)
		fmt.Printf("push failed for agent %s task %s: %v\n", agent.AgentID, task.TaskID, err)
	}

	return true
}

// sessionByTask finds the session owning a task. Used for logging only.
func sessionByTask(task *state.PhaseTask) string {
	for _, s := range state.GetAllSessions() {
		if s.GetTask(task.TaskID) != nil {
			return s.SessionID
		}
	}
	return ""
}
