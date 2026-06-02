package scheduler

import (
	"fmt"
	"os"
	"strconv"
	"time"

	"github.com/fluorine/designdoc-mcp/probe/internal/logger"
	"github.com/fluorine/designdoc-mcp/probe/internal/phase"
	"github.com/fluorine/designdoc-mcp/probe/internal/state"
)

func getRegisteredTimeout() time.Duration {
	if v := os.Getenv("PROBEMCP_REGISTERED_TIMEOUT"); v != "" {
		if d, err := strconv.Atoi(v); err == nil {
			return time.Duration(d) * time.Second
		}
	}
	return 10 * time.Second
}

// StartScheduler launches the background tick loop.
func StartScheduler() {
	go func() {
		for {
			time.Sleep(1 * time.Second)
			TickAllSessions()
		}
	}()
}

func TickAllSessions() {
	for _, s := range state.GetActiveSessions() {
		tickSession(s)
	}
}

func tickSession(s *state.MultiAgentSession) {
	phaseStr := s.GetPhase()

	switch phaseStr {
	case state.PhaseRegistered:
		tickRegistered(s)
	case state.PhaseProposal:
		tickPhase(s, state.PhaseProposal, state.PhaseChallenge)
	case state.PhaseChallenge:
		tickPhase(s, state.PhaseChallenge, state.PhaseRevision)
	case state.PhaseRevision:
		tickPhase(s, state.PhaseRevision, state.PhaseConsensus)
	case state.PhaseConsensus:
		tickPhase(s, state.PhaseConsensus, state.PhaseComplete)
	case state.PhaseComplete, state.PhaseFailedTimeout:
		// Terminal state — nothing to do.
	}
}

// tickRegistered decides when to advance from REGISTERED to PROPOSAL.
// Only advances when ManuallyStarted is set (via UI or API).
// A safety timeout (5 min) still fails empty sessions.
func tickRegistered(s *state.MultiAgentSession) {
	if s.AgentCount() == 0 && time.Since(s.CreatedAt) > 5*time.Minute {
		s.SetPhase(state.PhaseFailedTimeout)
		logger.LogTimeline(s.SessionID, "session_failed", state.PhaseFailedTimeout, "")
		logger.WriteSessionReport(s, "FAIL")
		return
	}
	if s.IsManuallyStarted() {
		phase.EnterPhase(s, state.PhaseProposal)
	}
}

// tickPhase handles push, retry, degraded marking, and barrier checks
// for a single active phase.
func tickPhase(s *state.MultiAgentSession, currentPhase, nextPhase string) {
	// If no active agents remain, fail the session immediately.
	if s.ActiveAgentCount() == 0 {
		s.SetPhase(state.PhaseFailedTimeout)
		logger.LogTimeline(s.SessionID, "session_failed", state.PhaseFailedTimeout, "")
		logger.WriteSessionReport(s, "FAIL")
		fmt.Printf("[SESSION %s] All agents degraded, session failed\n", s.SessionID)
		return
	}

	tasks := s.GetTasksForPhase(currentPhase)
	if len(tasks) == 0 {
		// Safety net: if no tasks exist, re-enter the phase.
		phase.EnterPhase(s, currentPhase)
		return
	}

	for _, task := range tasks {
		agent := s.GetAgent(task.AgentID)
		if agent == nil || agent.GetStatus() != "active" {
			continue
		}
		if task.Responded {
			continue
		}

		if task.PushCount == 0 {
			phase.PushTask(task, agent)
			continue
		}

		// Already pushed before; check timeout for re-push.
		if time.Since(task.LastPushAt) > 30*time.Second {
			if task.PushCount < 3 {
				phase.PushTask(task, agent)
			} else {
				agent.SetStatus("degraded")
				logger.LogTimeline(s.SessionID, "agent_degraded", currentPhase, task.TaskID)
				logger.LogEvent(s.SessionID, "agent_degraded", map[string]any{
					"agent_id": agent.AgentID,
					"phase":    currentPhase,
					"task_id":  task.TaskID,
					"retries":  task.PushCount,
				})
				fmt.Printf("[SESSION %s] Agent %s degraded after 3 retries in phase %s\n",
					s.SessionID, agent.AgentID, currentPhase)
			}
		}
	}

	// Barrier check.
	if state.CheckBarrier(s) {
		if nextPhase == state.PhaseComplete {
			s.SetPhase(state.PhaseComplete)
			s.SetComplete()
			logger.LogTimeline(s.SessionID, "session_complete", state.PhaseComplete, "")
			logger.WriteSessionReport(s, state.ComputeResult(s))
		} else {
			phase.EnterPhase(s, nextPhase)
		}
	}
}
