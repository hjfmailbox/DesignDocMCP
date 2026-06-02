package orchestrator

import (
	"fmt"
	"time"

	"github.com/fluorine/designdoc-mcp/probe/internal/logger"
	"github.com/fluorine/designdoc-mcp/probe/internal/phase"
	"github.com/fluorine/designdoc-mcp/probe/internal/state"
)

// Orchestrator drives a debate session from REGISTERED through all
// phases to COMPLETE using one-shot agent invocation.
// It owns phase advancement, task generation, and result aggregation.
type Orchestrator struct {
	Spawner  Spawner
	Observer Observer
}

// RunSession executes the full debate lifecycle for a single session.
// It advances through Proposal → Challenge → Revision → Consensus,
// spawning an agent for each phase and waiting for the barrier.
// When finished it marks the session COMPLETE and writes the report.
func (o *Orchestrator) RunSession(sessionID string) error {
	session := state.GetSession(sessionID)
	if session == nil {
		return fmt.Errorf("session not found: %s", sessionID)
	}

	phases := []string{
		state.PhaseProposal,
		state.PhaseChallenge,
		state.PhaseRevision,
		state.PhaseConsensus,
	}

	for _, ph := range phases {
		if err := o.runPhase(session, ph); err != nil {
			return fmt.Errorf("phase %s failed: %w", ph, err)
		}
	}

	session.SetPhase(state.PhaseComplete)
	session.SetComplete()
	logger.LogTimeline(sessionID, "session_complete", state.PhaseComplete, "")
	logger.WriteSessionReport(session, state.ComputeResult(session))

	return nil
}

func (o *Orchestrator) runPhase(session *state.MultiAgentSession, ph string) error {
	phase.EnterPhase(session, ph)

	agents := session.GetAgents()
	for _, agent := range agents {
		if agent.GetStatus() != "active" {
			continue
		}
		task := findTaskForAgent(session, agent.AgentID, ph)
		if task == nil {
			continue
		}
		if err := o.Spawner.Spawn(session.SessionID, agent.AgentID, ph, task.TaskID); err != nil {
			return err
		}
	}

	ok, err := o.Observer.WaitForBarrier(session.SessionID, 30*time.Second)
	if err != nil {
		return err
	}
	if !ok {
		return fmt.Errorf("barrier timeout in phase %s", ph)
	}

	return nil
}

func findTaskForAgent(session *state.MultiAgentSession, agentID, ph string) *state.PhaseTask {
	for _, t := range session.GetTasksForPhase(ph) {
		if t.AgentID == agentID {
			return t
		}
	}
	return nil
}
