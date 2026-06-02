package orchestrator

import (
	"context"
	"fmt"
	"time"

	"github.com/fluorine/designdoc-mcp/probe/internal/server"
	"github.com/fluorine/designdoc-mcp/probe/internal/state"
)

// Spawner abstracts how an agent process is invoked.
// The orchestrator calls Spawn for every active agent in a phase,
// then waits for the barrier.
type Spawner interface {
	Spawn(sessionID, agentID, phase, taskID string) error
}

// MockSpawner simulates a one-shot agent execution in a goroutine.
// It directly invokes the server submit handlers (same as a real agent
// would via MCP) and then "exits" — satisfying the R2-A2 requirement
// that no long-running worker remains.
type MockSpawner struct{}

func (m *MockSpawner) Spawn(sessionID, agentID, phase, taskID string) error {
	go func() {
		// Simulate agent work latency (small, deterministic).
		time.Sleep(50 * time.Millisecond)

		// Directly invoke the same handlers a real agent would call.
		// Context and MCP request are nil because the handlers do not
		// use them for submit operations (only register needs the session).
		var err error
		switch phase {
		case state.PhaseProposal:
			_, _, err = server.HandleSubmitProposal(context.Background(), nil, server.SubmitProposalInput{
				AgentID: agentID,
				TaskID:  taskID,
			})
		case state.PhaseChallenge:
			_, _, err = server.HandleSubmitChallenge(context.Background(), nil, server.SubmitChallengeInput{
				AgentID: agentID,
				TaskID:  taskID,
			})
		case state.PhaseRevision:
			_, _, err = server.HandleSubmitRevision(context.Background(), nil, server.SubmitRevisionInput{
				AgentID: agentID,
				TaskID:  taskID,
			})
		case state.PhaseConsensus:
			_, _, err = server.HandleSubmitConsensus(context.Background(), nil, server.SubmitConsensusInput{
				AgentID: agentID,
				TaskID:  taskID,
			})
		default:
			err = fmt.Errorf("unknown phase: %s", phase)
		}

		if err != nil {
			fmt.Printf("[MockSpawner] submit error for %s phase %s: %v\n", agentID, phase, err)
		}
	}()
	return nil
}
