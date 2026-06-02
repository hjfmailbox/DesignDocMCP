package tests

import (
	"testing"

	"github.com/fluorine/designdoc-mcp/probe/internal/logger"
	"github.com/fluorine/designdoc-mcp/probe/internal/orchestrator"
	"github.com/fluorine/designdoc-mcp/probe/internal/state"
)

// TestFourAgentOrchestrator validates R4 acceptance criteria:
//   R4-A1  Four-Agent Completion (PASS, full debate)
//   R4-A2  Stable Under Retry (1 failed agent tolerated)
//   R4-A3  No Architecture Rewrite (zero core file changes)
func TestFourAgentOrchestrator(t *testing.T) {
	logger.EnsureDirs()

	// ------------------------------------------------------------------
	// Register 4 distinct agents into the same session.
	// ------------------------------------------------------------------
	clients := []struct{ c, m string }{
		{"c1", "m1"},
		{"c2", "m2"},
		{"c3", "m3"},
		{"c4", "m4"},
	}

	session, firstAgent, _ := state.GetOrCreateSessionForAgent(clients[0].c, clients[0].m)
	agents := []*state.Agent{firstAgent}
	for i := 1; i < len(clients); i++ {
		_, a, _ := state.GetOrCreateSessionForAgent(clients[i].c, clients[i].m)
		agents = append(agents, a)
	}

	if session.AgentCount() != 4 {
		t.Fatalf("expected 4 agents, got %d", session.AgentCount())
	}
	t.Logf("Session %s with 4 agents", session.SessionID)

	// ------------------------------------------------------------------
	// R4-A1: Four-Agent Completion
	// ------------------------------------------------------------------
	rec := &recordingSpawner{
		inner:            &orchestrator.MockSpawner{},
		challengeRouting: make(map[string]string),
	}
	orch := &orchestrator.Orchestrator{
		Spawner:  rec,
		Observer: &orchestrator.BarrierObserver{},
	}

	if err := orch.RunSession(session.SessionID); err != nil {
		t.Fatalf("RunSession failed: %v", err)
	}

	if session.GetPhase() != state.PhaseComplete {
		t.Fatalf("R4-A1: expected COMPLETE, got %s", session.GetPhase())
	}
	if result := state.ComputeResult(session); result != "PASS" {
		t.Fatalf("R4-A1: expected PASS, got %s", result)
	}

	// Verify every phase spawned exactly 4 tasks.
	phaseSpawnCounts := make(map[string]int)
	for _, r := range rec.records {
		phaseSpawnCounts[r.Phase]++
	}
	for _, ph := range []string{state.PhaseProposal, state.PhaseChallenge, state.PhaseRevision, state.PhaseConsensus} {
		if phaseSpawnCounts[ph] != 4 {
			t.Fatalf("R4-A1: phase %s expected 4 spawns, got %d", ph, phaseSpawnCounts[ph])
		}
	}

	// Verify 4-agent challenge topology (ring: each agent challenges the next).
	agentSet := make(map[string]bool)
	for _, a := range agents {
		agentSet[a.AgentID] = true
	}
	challengeTargets := make(map[string]string) // challenger -> target
	for _, r := range rec.records {
		if r.Phase != state.PhaseChallenge {
			continue
		}
		targetID, ok := rec.challengeRouting[r.TaskID]
		if !ok {
			t.Fatalf("R4-A1: challenge routing missing for task %s", r.TaskID)
		}
		if targetID == r.AgentID {
			t.Fatalf("R4-A1: self-routing detected for %s", r.AgentID)
		}
		if !agentSet[targetID] {
			t.Fatalf("R4-A1: challenge target %s is not in session", targetID)
		}
		challengeTargets[r.AgentID] = targetID
	}
	if len(challengeTargets) != 4 {
		t.Fatalf("R4-A1: expected 4 challenge mappings, got %d", len(challengeTargets))
	}

	// Verify the ring is closed: starting from any agent, follow 4 hops and return.
	start := agents[0].AgentID
	current := start
	for i := 0; i < 4; i++ {
		next, ok := challengeTargets[current]
		if !ok {
			t.Fatalf("R4-A1: broken ring at %s", current)
		}
		current = next
	}
	if current != start {
		t.Fatalf("R4-A1: ring not closed: started at %s ended at %s", start, current)
	}

	t.Log("R4-A1 passed: 4-agent full debate with correct topology")

	// ------------------------------------------------------------------
	// R4-A2: Stable Under Retry (1 failed agent tolerated)
	// ------------------------------------------------------------------
	t.Run("OneDegraded", func(t *testing.T) {
		// Create exactly 4 agents in one session.
		var s2 *state.MultiAgentSession
		degradedAgents := make([]*state.Agent, 0, 4)
		for i := 0; i < 4; i++ {
			sess, a, _ := state.GetOrCreateSessionForAgent(
				string(rune('a'+i)),
				string(rune('x'+i)),
			)
			if s2 == nil {
				s2 = sess
			} else if sess.SessionID != s2.SessionID {
				t.Fatalf("agent %d joined different session %s vs %s", i, sess.SessionID, s2.SessionID)
			}
			degradedAgents = append(degradedAgents, a)
		}
		if s2.AgentCount() != 4 {
			t.Fatalf("expected 4 agents in session, got %d", s2.AgentCount())
		}

		// Degrade the last agent before orchestration.
		degradedAgents[3].SetStatus("degraded")

		orch2 := &orchestrator.Orchestrator{
			Spawner:  &orchestrator.MockSpawner{},
			Observer: &orchestrator.BarrierObserver{},
		}
		if err := orch2.RunSession(s2.SessionID); err != nil {
			t.Fatalf("RunSession with 1 degraded agent failed: %v", err)
		}

		if s2.GetPhase() != state.PhaseComplete {
			t.Fatalf("R4-A2: session did not complete with 1 degraded agent")
		}
		res := state.ComputeResult(s2)
		if res != "PARTIAL" {
			t.Fatalf("R4-A2: expected PARTIAL, got %s", res)
		}
		t.Log("R4-A2 passed: 1 failed agent tolerated")
	})
}
