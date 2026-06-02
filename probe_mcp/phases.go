package main

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

const phasePushTimeout = 30 * time.Second

var actionMap = map[string]string{
	PhaseProposal:  "submit_proposal",
	PhaseChallenge: "submit_challenge",
	PhaseRevision:  "submit_revision",
	PhaseConsensus: "submit_consensus",
}

// enterPhase creates tasks for every active agent in the session.
// For challenge phase, tasks include a fixed topology target.
func enterPhase(session *MultiAgentSession, phase string) {
	session.ClearTasks()
	session.SetPhase(phase)

	agents := session.GetAgents()
	for _, agent := range agents {
		if agent.GetStatus() != "active" {
			continue
		}

		taskID := "task_" + randomHex(6)
		task := &PhaseTask{
			TaskID:  taskID,
			Phase:   phase,
			AgentID: agent.AgentID,
		}

		if phase == PhaseChallenge {
			task.TargetID = session.GetChallengeTarget(agent.AgentID)
		}

		session.AddTask(task)
		logTimeline(session.SessionID, "task_created", phase, taskID)
	}

	logTimeline(session.SessionID, "phase_started", phase, "")
}

// pushTask sends an MCP logging push to the agent's ServerSession.
// Returns true if the push was attempted (regardless of transport error).
func pushTask(task *PhaseTask, agent *Agent) bool {
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

	logNotificationSent(sessionID, agent.AgentID, agent.DisplayName, task.Phase, task.TaskID, "logging/message", payload)

	err := ss.Log(ctx, &mcp.LoggingMessageParams{
		Level:  mcp.LoggingLevel("info"),
		Data:   string(data),
		Logger: "MiniDebateRuntime",
	})

	task.IncrementPush()
	logPush(sessionID, task.Phase, task.TaskID, task.PushCount)

	if err != nil {
		logTimeline(sessionID, "push_failed", task.Phase, task.TaskID)
		fmt.Printf("push failed for agent %s task %s: %v\n", agent.AgentID, task.TaskID, err)
	}

	return true
}

// sessionByTask finds the session owning a task. Used for logging only.
func sessionByTask(task *PhaseTask) string {
	for _, s := range getAllSessions() {
		if s.GetTask(task.TaskID) != nil {
			return s.SessionID
		}
	}
	return ""
}
