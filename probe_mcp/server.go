package main

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// ---------------------------------------------------------------------------
// Input / Output types
// ---------------------------------------------------------------------------

type RegisterAgentInput struct {
	Client string `json:"client"`
	Model  string `json:"model"`
}

type RegisterAgentOutput struct {
	AgentID     string `json:"agent_id"`
	SessionID   string `json:"session_id"`
	DisplayName string `json:"display_name"`
}

type PhaseSubmission struct {
	AgentID string         `json:"agent_id"`
	TaskID  string         `json:"task_id"`
	Content map[string]any `json:"content,omitempty"`
}

type SubmitProposalInput PhaseSubmission
type SubmitChallengeInput PhaseSubmission
type SubmitRevisionInput PhaseSubmission
type SubmitConsensusInput PhaseSubmission

type SubmitPhaseOutput struct {
	Status string `json:"status"`
}

type GenerateReportInput struct {
	SessionID string `json:"session_id,omitempty"`
}

type GenerateReportOutput struct {
	Report string `json:"report"`
}

type GetRuntimeStatusInput struct {
	AgentID string `json:"agent_id"`
}

type GetRuntimeStatusOutput struct {
	Registered  bool   `json:"registered"`
	SessionID   string `json:"session_id"`
	AgentID     string `json:"agent_id"`
	DisplayName string `json:"display_name"`
	Phase       string `json:"phase"`
	TaskID      string `json:"task_id"`
	NeedsSubmit bool   `json:"needs_submit"`
}

// ---------------------------------------------------------------------------
// Tool handlers
// ---------------------------------------------------------------------------

func handleRegisterAgent(_ context.Context, req *mcp.CallToolRequest, in RegisterAgentInput) (*mcp.CallToolResult, RegisterAgentOutput, error) {
	session, agent, isNew := getOrCreateSessionForAgent(in.Client, in.Model)
	agent.SetServerSession(req.Session)

	connID := randomHex(8)
	agent.SetConnected(true, connID)
	logClientEvent(agent.AgentID, agent.DisplayName, "client_connected", connID)
	writeConnectedClients(session.GetAgents())

	if isNew {
		logTimeline(session.SessionID, "session_created", session.GetPhase(), "")
	}

	logTimeline(session.SessionID, "agent_joined", session.GetPhase(), "")
	logEvent(session.SessionID, "agent_joined", map[string]any{
		"agent_id":     agent.AgentID,
		"display_name": agent.DisplayName,
		"ready_count":  session.AgentCount(),
		"max_agents":   MaxAgents,
	})

	out := RegisterAgentOutput{
		AgentID:     agent.AgentID,
		SessionID:   session.SessionID,
		DisplayName: agent.DisplayName,
	}
	return nil, out, nil
}

func handleSubmitProposal(_ context.Context, _ *mcp.CallToolRequest, in SubmitProposalInput) (*mcp.CallToolResult, SubmitPhaseOutput, error) {
	return handlePhaseSubmit(in.AgentID, in.TaskID, PhaseProposal)
}

func handleSubmitChallenge(_ context.Context, _ *mcp.CallToolRequest, in SubmitChallengeInput) (*mcp.CallToolResult, SubmitPhaseOutput, error) {
	return handlePhaseSubmit(in.AgentID, in.TaskID, PhaseChallenge)
}

func handleSubmitRevision(_ context.Context, _ *mcp.CallToolRequest, in SubmitRevisionInput) (*mcp.CallToolResult, SubmitPhaseOutput, error) {
	return handlePhaseSubmit(in.AgentID, in.TaskID, PhaseRevision)
}

func handleSubmitConsensus(_ context.Context, _ *mcp.CallToolRequest, in SubmitConsensusInput) (*mcp.CallToolResult, SubmitPhaseOutput, error) {
	return handlePhaseSubmit(in.AgentID, in.TaskID, PhaseConsensus)
}

func handlePhaseSubmit(agentID, taskID, expectedPhase string) (*mcp.CallToolResult, SubmitPhaseOutput, error) {
	session := getSessionByAgentID(agentID)
	if session == nil {
		return nil, SubmitPhaseOutput{Status: "unknown_agent"}, nil
	}

	task := session.GetTask(taskID)
	if task == nil {
		logResponse(session.SessionID, expectedPhase, taskID, agentID, "unknown_task")
		return nil, SubmitPhaseOutput{Status: "unknown_task_id"}, nil
	}

	// Idempotency check.
	if task.Responded {
		logResponse(session.SessionID, expectedPhase, taskID, agentID, "duplicate")
		return nil, SubmitPhaseOutput{Status: "already_done"}, nil
	}

	// Phase + agent validation.
	if task.Phase != expectedPhase {
		logResponse(session.SessionID, expectedPhase, taskID, agentID, "wrong_phase")
		return nil, SubmitPhaseOutput{Status: fmt.Sprintf("wrong_phase: expected %s, got %s", expectedPhase, task.Phase)}, nil
	}
	if task.AgentID != agentID {
		logResponse(session.SessionID, expectedPhase, taskID, agentID, "wrong_agent")
		return nil, SubmitPhaseOutput{Status: "wrong_agent_id"}, nil
	}

	task.MarkResponded()
	logResponse(session.SessionID, expectedPhase, taskID, agentID, "success")
	return nil, SubmitPhaseOutput{Status: "success"}, nil
}

func handleGetRuntimeStatus(_ context.Context, _ *mcp.CallToolRequest, in GetRuntimeStatusInput) (*mcp.CallToolResult, GetRuntimeStatusOutput, error) {
	session := getSessionByAgentID(in.AgentID)
	if session == nil {
		out := GetRuntimeStatusOutput{Registered: false}
		return nil, out, nil
	}

	agent := session.GetAgent(in.AgentID)
	if agent == nil {
		out := GetRuntimeStatusOutput{Registered: false}
		return nil, out, nil
	}

	phase := session.GetPhase()
	taskID := ""
	needsSubmit := false

	for _, t := range session.GetTasksForPhase(phase) {
		if t.AgentID == in.AgentID {
			taskID = t.TaskID
			needsSubmit = !t.Responded
			break
		}
	}

	out := GetRuntimeStatusOutput{
		Registered:  true,
		SessionID:   session.SessionID,
		AgentID:     agent.AgentID,
		DisplayName: agent.DisplayName,
		Phase:       phase,
		TaskID:      taskID,
		NeedsSubmit: needsSubmit,
	}
	return nil, out, nil
}

func handleGenerateReport(_ context.Context, _ *mcp.CallToolRequest, in GenerateReportInput) (*mcp.CallToolResult, GenerateReportOutput, error) {
	var list []*MultiAgentSession
	if in.SessionID != "" {
		if s := getSession(in.SessionID); s != nil {
			list = append(list, s)
		}
	} else {
		list = getAllSessions()
	}

	var rows []string
	for _, s := range list {
		pc := s.CompletedPhases
		result := computeResult(s)
		if s.GetPhase() == PhaseFailedTimeout {
			result = "FAIL"
		}

		agents := s.GetAgents()
		agentNames := make([]string, len(agents))
		for i, a := range agents {
			agentNames[i] = a.DisplayName
		}

		row := fmt.Sprintf("| %s | %s | %s | %s | %s | %s | %s | %s |",
			s.SessionID,
			strings.Join(agentNames, ", "),
			boolStr(pc[PhaseProposal]),
			boolStr(pc[PhaseChallenge]),
			boolStr(pc[PhaseRevision]),
			boolStr(pc[PhaseConsensus]),
			s.GetPhase(),
			result,
		)
		rows = append(rows, row)
	}

	header := "| Session | Agents | Proposal | Challenge | Revision | Consensus | Phase | Result |"
	sep := "|---|---|---|---|---|---|---|---|"

	var body string
	if len(rows) == 0 {
		body = "| (none) | - | - | - | - | - | - | - |\n"
	} else {
		body = strings.Join(rows, "\n") + "\n"
	}

	report := fmt.Sprintf(
		"# Mini Debate Runtime Report\n\n%s\n%s\n%s\n\n**Notes**\n"+
			"- *Result*: PASS = all agents active, PARTIAL = some degraded, FAIL = all degraded.\n"+
			"- Phases advance via barrier: all active agents must respond.\n",
		header, sep, body,
	)

	return nil, GenerateReportOutput{Report: report}, nil
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func boolStr(b bool) string {
	if b {
		return "Yes"
	}
	return "No"
}

// marshalResult builds a JSON text block for tool results.
func marshalResult(v any) string {
	b, _ := json.Marshal(v)
	return string(b)
}
