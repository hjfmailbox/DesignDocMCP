package main

import (
	"fmt"
	"os"
	"strconv"
	"time"
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
			tickAllSessions()
		}
	}()
}

func tickAllSessions() {
	for _, s := range getActiveSessions() {
		tickSession(s)
	}
}

func tickSession(s *MultiAgentSession) {
	phase := s.GetPhase()

	switch phase {
	case PhaseRegistered:
		tickRegistered(s)
	case PhaseProposal:
		tickPhase(s, PhaseProposal, PhaseChallenge)
	case PhaseChallenge:
		tickPhase(s, PhaseChallenge, PhaseRevision)
	case PhaseRevision:
		tickPhase(s, PhaseRevision, PhaseConsensus)
	case PhaseConsensus:
		tickPhase(s, PhaseConsensus, PhaseComplete)
	case PhaseComplete, PhaseFailedTimeout:
		// Terminal state — nothing to do.
	}
}

// tickRegistered decides when to advance from REGISTERED to PROPOSAL.
// Only advances when ManuallyStarted is set (via UI or API).
// A safety timeout (5 min) still fails empty sessions.
func tickRegistered(s *MultiAgentSession) {
	if s.AgentCount() == 0 && time.Since(s.CreatedAt) > 5*time.Minute {
		s.SetPhase(PhaseFailedTimeout)
		logTimeline(s.SessionID, "session_failed", PhaseFailedTimeout, "")
		writeSessionReport(s, "FAIL")
		return
	}
	if s.IsManuallyStarted() {
		enterPhase(s, PhaseProposal)
	}
}

// tickPhase handles push, retry, degraded marking, and barrier checks
// for a single active phase.
func tickPhase(s *MultiAgentSession, currentPhase, nextPhase string) {
	// If no active agents remain, fail the session immediately.
	if s.ActiveAgentCount() == 0 {
		s.SetPhase(PhaseFailedTimeout)
		logTimeline(s.SessionID, "session_failed", PhaseFailedTimeout, "")
		writeSessionReport(s, "FAIL")
		fmt.Printf("[SESSION %s] All agents degraded, session failed\n", s.SessionID)
		return
	}

	tasks := s.GetTasksForPhase(currentPhase)
	if len(tasks) == 0 {
		// Safety net: if no tasks exist, re-enter the phase.
		enterPhase(s, currentPhase)
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
			pushTask(task, agent)
			continue
		}

		// Already pushed before; check timeout for re-push.
		if time.Since(task.LastPushAt) > phasePushTimeout {
			if task.PushCount < 3 {
				pushTask(task, agent)
			} else {
				agent.SetStatus("degraded")
				logTimeline(s.SessionID, "agent_degraded", currentPhase, task.TaskID)
				logEvent(s.SessionID, "agent_degraded", map[string]any{
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
	if checkBarrier(s) {
		if nextPhase == PhaseComplete {
			s.SetPhase(PhaseComplete)
			s.SetComplete()
			logTimeline(s.SessionID, "session_complete", PhaseComplete, "")
			writeSessionReport(s, computeResult(s))
		} else {
			enterPhase(s, nextPhase)
		}
	}
}

// computeResult determines the session outcome.
// PASS   = no agents degraded.
// PARTIAL = some agents degraded but session reached COMPLETE.
// FAIL   = all agents degraded (or session never started).
func computeResult(s *MultiAgentSession) string {
	agents := s.GetAgents()
	if len(agents) == 0 {
		return "FAIL"
	}
	degradedCount := 0
	for _, a := range agents {
		if a.GetStatus() == "degraded" {
			degradedCount++
		}
	}
	if degradedCount == len(agents) {
		return "FAIL"
	}
	if degradedCount > 0 {
		return "PARTIAL"
	}
	return "PASS"
}
