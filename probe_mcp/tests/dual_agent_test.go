package tests

import (
	"testing"

	"github.com/fluorine/designdoc-mcp/probe/internal/logger"
	"github.com/fluorine/designdoc-mcp/probe/internal/orchestrator"
	"github.com/fluorine/designdoc-mcp/probe/internal/state"
)

// spawnRecord captures what the orchestrator asked the spawner to do.
type spawnRecord struct {
	SessionID string
	AgentID   string
	Phase     string
	TaskID    string
}

// recordingSpawner wraps MockSpawner and logs every Spawn call.
// It also captures challenge routing immediately (before the next phase
// clears the tasks).
type recordingSpawner struct {
	inner   *orchestrator.MockSpawner
	records []spawnRecord
	// challengeRouting maps taskID -> targetID observed at spawn time.
	challengeRouting map[string]string
}

func (r *recordingSpawner) Spawn(sessionID, agentID, phase, taskID string) error {
	r.records = append(r.records, spawnRecord{SessionID: sessionID, AgentID: agentID, Phase: phase, TaskID: taskID})

	if phase == state.PhaseChallenge {
		sess := state.GetSession(sessionID)
		if sess != nil {
			if task := sess.GetTask(taskID); task != nil {
				r.challengeRouting[taskID] = task.TargetID
			}
		}
	}

	return r.inner.Spawn(sessionID, agentID, phase, taskID)
}

// TestDualAgentOrchestrator validates R3 acceptance criteria:
//   R3-A1  Correct challenge routing (A→B, B→A)
//   R3-A2  Barrier logic (phase advances only when all required agents submit)
//   R3-A3  Failure isolation (1 degraded agent does not deadlock)
func TestDualAgentOrchestrator(t *testing.T) {
	logger.EnsureDirs()

	// ------------------------------------------------------------------
	// Register 2 distinct agents into the same session.
	// Agent 1 creates a new REGISTERED session.
	// Agent 2 finds the same REGISTERED session and joins it.
	// ------------------------------------------------------------------
	session, agentA, _ := state.GetOrCreateSessionForAgent("client-a", "model-a")
	_, agentB, _ := state.GetOrCreateSessionForAgent("client-b", "model-b")
	if session == nil || agentA == nil || agentB == nil {
		t.Fatal("failed to create session with 2 agents")
	}
	if agentA.AgentID == agentB.AgentID {
		t.Fatal("agents collapsed into single id")
	}
	t.Logf("Session %s: agentA=%s agentB=%s", session.SessionID, agentA.AgentID, agentB.AgentID)

	rec := &recordingSpawner{inner: &orchestrator.MockSpawner{}, challengeRouting: make(map[string]string)}
	orch := &orchestrator.Orchestrator{
		Spawner:  rec,
		Observer: &orchestrator.BarrierObserver{},
	}

	if err := orch.RunSession(session.SessionID); err != nil {
		t.Fatalf("RunSession failed: %v", err)
	}

	// ------------------------------------------------------------------
	// R3-A1: Correct Routing
	// ------------------------------------------------------------------
	var challengeCount int
	for _, r := range rec.records {
		if r.Phase != state.PhaseChallenge {
			continue
		}
		challengeCount++
		targetID, ok := rec.challengeRouting[r.TaskID]
		if !ok {
			t.Fatalf("R3-A1: challenge task %s routing not captured", r.TaskID)
		}
		if targetID == "" {
			t.Fatalf("R3-A1: challenge task %s has empty target", r.TaskID)
		}
		if targetID == r.AgentID {
			t.Fatalf("R3-A1: self-routing bug: agent %s challenged itself", r.AgentID)
		}
		// Verify the target is the *other* agent in this 2-agent session.
		if targetID != agentA.AgentID && targetID != agentB.AgentID {
			t.Fatalf("R3-A1: challenge target %s is not a known agent", targetID)
		}
		t.Logf("R3-A1: %s challenges %s", r.AgentID, targetID)
	}
	if challengeCount != 2 {
		t.Fatalf("R3-A1: expected 2 challenge spawns, got %d", challengeCount)
	}
	t.Log("R3-A1 passed: correct routing, no self-routing")

	// ------------------------------------------------------------------
	// R3-A2: Barrier Logic
	// ------------------------------------------------------------------
	if session.GetPhase() != state.PhaseComplete {
		t.Fatalf("R3-A2: expected COMPLETE, got %s", session.GetPhase())
	}
	result := state.ComputeResult(session)
	if result != "PASS" {
		t.Fatalf("R3-A2: expected PASS, got %s", result)
	}
	for _, ph := range []string{state.PhaseProposal, state.PhaseChallenge, state.PhaseRevision, state.PhaseConsensus} {
		if !session.CompletedPhases[ph] {
			t.Fatalf("R3-A2: phase %s not completed", ph)
		}
	}
	t.Log("R3-A2 passed: barrier held until all agents submitted")

	// ------------------------------------------------------------------
	// R3-A3: Failure Isolation (sub-test)
	// ------------------------------------------------------------------
	t.Run("DegradedAgent", func(t *testing.T) {
		// Fresh session with 2 agents.
		s2, _, _ := state.GetOrCreateSessionForAgent("client-c", "model-c")
		_, a2, _ := state.GetOrCreateSessionForAgent("client-d", "model-d")

		// Degrade agent 2 before orchestration starts.
		a2.SetStatus("degraded")

		orch2 := &orchestrator.Orchestrator{
			Spawner:  &orchestrator.MockSpawner{},
			Observer: &orchestrator.BarrierObserver{},
		}
		if err := orch2.RunSession(s2.SessionID); err != nil {
			t.Fatalf("RunSession with degraded agent failed: %v", err)
		}

		if s2.GetPhase() != state.PhaseComplete {
			t.Fatalf("R3-A3: session did not complete with 1 degraded agent")
		}

		res := state.ComputeResult(s2)
		if res != "PARTIAL" {
			t.Fatalf("R3-A3: expected PARTIAL with 1 degraded agent, got %s", res)
		}
		t.Log("R3-A3 passed: degraded agent tolerated, session completes")
	})
}
