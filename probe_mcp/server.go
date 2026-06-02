package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

const phasePushTimeout = 30 * time.Second

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

// ---------------------------------------------------------------------------
// Tool handlers
// ---------------------------------------------------------------------------

func handleRegisterAgent(_ context.Context, req *mcp.CallToolRequest, in RegisterAgentInput) (*mcp.CallToolResult, RegisterAgentOutput, error) {
	session := createSession(in.Client, in.Model)

	logTimeline(session.SessionID, "session_created", session.Phase, "")

	// Capture session reference and launch phase loop.
	serverSession := req.Session
	go runPhaseLoop(session, serverSession)

	out := RegisterAgentOutput{
		AgentID:     session.AgentID,
		SessionID:   session.SessionID,
		DisplayName: session.DisplayName,
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
	s := getSessionByAgentID(agentID)
	if s == nil {
		return nil, SubmitPhaseOutput{Status: "unknown_agent"}, nil
	}

	// Idempotency check.
	if s.IsPhaseCompleted(taskID) {
		logResponse(s.SessionID, expectedPhase, taskID, agentID, "duplicate")
		return nil, SubmitPhaseOutput{Status: "already_done"}, nil
	}

	// Phase + task validation.
	if s.GetPhase() != expectedPhase {
		logResponse(s.SessionID, expectedPhase, taskID, agentID, "wrong_phase")
		return nil, SubmitPhaseOutput{Status: fmt.Sprintf("wrong_phase: expected %s, got %s", expectedPhase, s.GetPhase())}, nil
	}
	if s.GetCurrentTaskID() != taskID {
		logResponse(s.SessionID, expectedPhase, taskID, agentID, "wrong_task_id")
		return nil, SubmitPhaseOutput{Status: "wrong_task_id"}, nil
	}

	s.MarkPhaseCompleted(taskID)
	s.NotifyResponse()

	logResponse(s.SessionID, expectedPhase, taskID, agentID, "success")
	return nil, SubmitPhaseOutput{Status: "success"}, nil
}

func handleGenerateReport(_ context.Context, _ *mcp.CallToolRequest, in GenerateReportInput) (*mcp.CallToolResult, GenerateReportOutput, error) {
	var sessionsList []*DebateSession
	if in.SessionID != "" {
		if s := getSession(in.SessionID); s != nil {
			sessionsList = append(sessionsList, s)
		}
	} else {
		sessionsList = getAllSessions()
	}

	var rows []string
	for _, s := range sessionsList {
		pc := s.PhaseCompletions

		result := "FAIL"
		if s.GetPhase() == PhaseComplete {
			result = "PASS"
		}

		row := fmt.Sprintf("| %s | %s | %s | %s | %s | %s | %s | %s |",
			s.DisplayName,
			boolStr(s.Client != ""),
			boolStr(s.GetPhase() != PhaseRegistered && s.GetPhase() != PhaseFailedTimeout),
			boolStr(pc[PhaseProposal]),
			boolStr(pc[PhaseChallenge]),
			boolStr(pc[PhaseRevision]),
			boolStr(pc[PhaseConsensus]),
			result,
		)
		rows = append(rows, row)
	}

	header := "| Agent | Registered | Active | Proposal | Challenge | Revision | Consensus | Result |"
	sep := "|---|---|---|---|---|---|---|---|"

	var body string
	if len(rows) == 0 {
		body = "| (none) | - | - | - | - | - | - | - |\n"
	} else {
		body = strings.Join(rows, "\n") + "\n"
	}

	report := fmt.Sprintf(
		"# Mini Debate Runtime Report\n\n%s\n%s\n%s\n\n**Notes**\n"+
			"- *Active*: Session is not in REGISTERED or FAILED_TIMEOUT state.\n"+
			"- Phases are verified server-side by push-response loop.\n",
		header, sep, body,
	)

	return nil, GenerateReportOutput{Report: report}, nil
}

// ---------------------------------------------------------------------------
// Phase loop
// ---------------------------------------------------------------------------

func runPhaseLoop(s *DebateSession, serverSession *mcp.ServerSession) {
	phases := []string{PhaseProposal, PhaseChallenge, PhaseRevision, PhaseConsensus}
	actionMap := map[string]string{
		PhaseProposal:  "submit_proposal",
		PhaseChallenge: "submit_challenge",
		PhaseRevision:  "submit_revision",
		PhaseConsensus: "submit_consensus",
	}

	for _, phase := range phases {
		s.SetPhase(phase)
		taskID := "task_" + randomHex(6)
		s.SetCurrentTaskID(taskID)
		s.SetRetryCount(0)
		s.ResetResponseCh()

		logTimeline(s.SessionID, "phase_started", phase, taskID)

		responded := false
		for retry := 0; retry <= 3; retry++ {
			s.SetRetryCount(retry)

			ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
			pushData := map[string]any{
				"phase":           phase,
				"task_id":         taskID,
				"required_action": actionMap[phase],
				"retry":           retry,
			}
			pushJSON, _ := json.Marshal(pushData)

			err := serverSession.Log(ctx, &mcp.LoggingMessageParams{
				Level:  mcp.LoggingLevel("info"),
				Data:   string(pushJSON),
				Logger: "MiniDebateRuntime",
			})
			cancel()

			if err != nil {
				logPush(s.SessionID, phase, taskID, retry)
				logTimeline(s.SessionID, "push_failed", phase, taskID)
			} else {
				logPush(s.SessionID, phase, taskID, retry)
			}

			select {
			case <-s.ResponseCh:
				responded = true
				logTimeline(s.SessionID, "phase_completed", phase, taskID)
				break
			case <-time.After(phasePushTimeout):
				// timeout, continue to next retry
			}
			if responded {
				break
			}
		}

		if !responded {
			s.SetPhase(PhaseFailedTimeout)
			logTimeline(s.SessionID, "phase_timeout", phase, taskID)
			writeReport(s, "FAIL")
			return
		}
	}

	s.SetPhase(PhaseComplete)
	logTimeline(s.SessionID, "session_complete", PhaseComplete, "")
	writeReport(s, "PASS")
}

func writeReport(s *DebateSession, result string) {
	pc := s.PhaseCompletions
	report := map[string]any{
		"agent":      s.DisplayName,
		"client":     s.Client,
		"model":      s.Model,
		"session_id": s.SessionID,
		"connected":  true,
		"proposal":   pc[PhaseProposal],
		"challenge":  pc[PhaseChallenge],
		"revision":   pc[PhaseRevision],
		"consensus":  pc[PhaseConsensus],
		"result":     result,
	}

	// For completed sessions, we know all phases passed.
	if result == "PASS" {
		report["proposal"] = true
		report["challenge"] = true
		report["revision"] = true
		report["consensus"] = true
	}

	logReport(s.SessionID, report)
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func randomHex(n int) string {
	b := make([]byte, n/2+1)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)[:n]
}

func boolStr(b bool) string {
	if b {
		return "Yes"
	}
	return "No"
}
