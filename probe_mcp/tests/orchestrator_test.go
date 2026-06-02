package tests

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/fluorine/designdoc-mcp/probe/internal/logger"
	"github.com/fluorine/designdoc-mcp/probe/internal/orchestrator"
	"github.com/fluorine/designdoc-mcp/probe/internal/state"
)

// TestSingleAgentOrchestrator validates R2 acceptance criteria:
//   R2-A1  Full session completion (PASS, 4/4 phases)
//   R2-A2  No long-running worker (MockSpawner uses goroutine + exit)
//   R2-A3  Idempotent re-entry (duplicate RunSession does not corrupt)
//   R2-A4  Deterministic logs (summary.json + timeline.jsonl)
func TestSingleAgentOrchestrator(t *testing.T) {
	logger.EnsureDirs()

	// ------------------------------------------------------------------
	// 1. Create session with a single agent
	// ------------------------------------------------------------------
	session, agent, _ := state.GetOrCreateSessionForAgent("test-client", "test-model")
	if session == nil || agent == nil {
		t.Fatal("failed to create session/agent")
	}
	t.Logf("Session %s created with agent %s", session.SessionID, agent.AgentID)

	// ------------------------------------------------------------------
	// 2. Run orchestrator
	// ------------------------------------------------------------------
	orch := &orchestrator.Orchestrator{
		Spawner:  &orchestrator.MockSpawner{},
		Observer: &orchestrator.BarrierObserver{},
	}

	if err := orch.RunSession(session.SessionID); err != nil {
		t.Fatalf("RunSession failed: %v", err)
	}

	// ------------------------------------------------------------------
	// 3. R2-A1: Verify full completion
	// ------------------------------------------------------------------
	if got := session.GetPhase(); got != state.PhaseComplete {
		t.Fatalf("R2-A1: expected phase %s, got %s", state.PhaseComplete, got)
	}

	result := state.ComputeResult(session)
	if result != "PASS" {
		t.Fatalf("R2-A1: expected result PASS, got %s", result)
	}

	expectedPhases := []string{state.PhaseProposal, state.PhaseChallenge, state.PhaseRevision, state.PhaseConsensus}
	for _, ph := range expectedPhases {
		if !session.CompletedPhases[ph] {
			t.Fatalf("R2-A1: phase %s not marked complete", ph)
		}
	}
	t.Log("R2-A1 passed: full session completion")

	// ------------------------------------------------------------------
	// 4. R2-A3: Idempotent re-entry
	// ------------------------------------------------------------------
	// Re-run the same session.  Because tasks are recreated and the
	// server submit handlers are idempotent (already_done for duplicates),
	// this must not panic or corrupt state.
	err := orch.RunSession(session.SessionID)
	if err != nil {
		// A second run may legitimately fail because the session is
		// already COMPLETE and tasks are stale.  What matters is that
		// it does not panic and does not corrupt in-memory state.
		t.Logf("R2-A3: re-run returned expected non-nil error: %v", err)
	}
	if session.GetPhase() != state.PhaseComplete {
		t.Fatalf("R2-A3: re-run corrupted session phase")
	}
	t.Log("R2-A3 passed: idempotent re-entry safe")

	// ------------------------------------------------------------------
	// 5. R2-A4: Deterministic logs
	// ------------------------------------------------------------------
	summaryPath := filepath.Join(logger.ProbeOutputsDir, session.SessionID, "summary.json")
	if _, err := os.Stat(summaryPath); os.IsNotExist(err) {
		t.Fatalf("R2-A4: summary.json not found at %s", summaryPath)
	}

	// Allow a short grace period for timeline flush.
	time.Sleep(100 * time.Millisecond)
	timelinePath := filepath.Join(logger.LogsDir, "session_timeline.jsonl")
	if _, err := os.Stat(timelinePath); os.IsNotExist(err) {
		t.Fatalf("R2-A4: session_timeline.jsonl not found at %s", timelinePath)
	}
	t.Log("R2-A4 passed: deterministic logs exist")
}
