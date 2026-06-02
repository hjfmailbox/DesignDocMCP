package tests

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/fluorine/designdoc-mcp/probe/internal/state"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func TestSmokeGetRuntimeStatus(t *testing.T) {
	ctx := context.Background()

	client := mcp.NewClient(&mcp.Implementation{Name: "smoke-test", Version: "1.0.0"},
		&mcp.ClientOptions{
			LoggingMessageHandler: func(_ context.Context, req *mcp.LoggingMessageRequest) {
				// Drain push messages to prevent SDK blocking.
				_ = req.Params.Data
			},
		})
	transport := &mcp.StreamableClientTransport{Endpoint: "http://127.0.0.1:8799/mcp"}

	session, err := client.Connect(ctx, transport, nil)
	if err != nil {
		t.Fatalf("connect failed: %v", err)
	}
	defer session.Close()

	// ------------------------------------------------------------------
	// 1. Register 4 agents (fills one session)
	// ------------------------------------------------------------------
	var agentIDs []string
	var sessionID string
	models := []string{"smoke-a", "smoke-b", "smoke-c", "smoke-d"}

	for _, model := range models {
		res, err := session.CallTool(ctx, &mcp.CallToolParams{
			Name:      "register_agent",
			Arguments: map[string]any{"client": "smoke-client", "model": model},
		})
		if err != nil {
			t.Fatalf("register_agent(%s) failed: %v", model, err)
		}
		agID, sessID := extractIDs(res)
		if agID == "" || sessID == "" {
			t.Fatalf("missing ids for model %s", model)
		}
		if sessionID == "" {
			sessionID = sessID
		} else if sessID != sessionID {
			t.Fatalf("agents split across sessions: %s vs %s", sessionID, sessID)
		}
		agentIDs = append(agentIDs, agID)
		t.Logf("registered agent_id=%s session_id=%s", agID, sessID)
	}

	if len(agentIDs) != 4 {
		t.Fatalf("expected 4 agents, got %d", len(agentIDs))
	}
	t.Logf("all 4 agents in session %s", sessionID)

	// ------------------------------------------------------------------
	// 2. get_runtime_status (unknown agent)
	// ------------------------------------------------------------------
	res2, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name:      "get_runtime_status",
		Arguments: map[string]any{"agent_id": "nonexistent"},
	})
	if err != nil {
		t.Fatalf("get_runtime_status unknown failed: %v", err)
	}
	for _, c := range res2.Content {
		if text, ok := c.(*mcp.TextContent); ok {
			if !strings.Contains(text.Text, `"registered":false`) {
				t.Fatalf("expected registered=false for unknown agent, got: %s", text.Text)
			}
		}
	}

	// ------------------------------------------------------------------
	// 3. Poll first agent until phase advances (should be fast with 4 agents)
	// ------------------------------------------------------------------
	var finalPhase string
	for i := 0; i < 20; i++ {
		res, err := session.CallTool(ctx, &mcp.CallToolParams{
			Name:      "get_runtime_status",
			Arguments: map[string]any{"agent_id": agentIDs[0]},
		})
		if err != nil {
			t.Fatalf("poll failed: %v", err)
		}
		for _, c := range res.Content {
			if text, ok := c.(*mcp.TextContent); ok {
				finalPhase = extractFromJSON(text.Text, "phase")
				if finalPhase != state.PhaseRegistered {
					t.Logf("poll %d: phase=%s", i, finalPhase)
					goto phaseAdvanced
				}
			}
		}
		time.Sleep(500 * time.Millisecond)
	}
	t.Fatalf("phase did not advance after 10s, still %s", finalPhase)

phaseAdvanced:
	if finalPhase != state.PhaseProposal {
		t.Fatalf("expected phase PROPOSAL after registration fill, got: %s", finalPhase)
	}

	// ------------------------------------------------------------------
	// 4. Idempotent register — same client+model returns same agent
	// ------------------------------------------------------------------
	res4, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name:      "register_agent",
		Arguments: map[string]any{"client": "smoke-client", "model": "smoke-a"},
	})
	if err != nil {
		t.Fatalf("idempotent register failed: %v", err)
	}
	agID4, _ := extractIDs(res4)
	if agID4 != agentIDs[0] {
		t.Fatalf("idempotency broken: first=%s second=%s", agentIDs[0], agID4)
	}
	t.Log("idempotency OK")

	t.Log("SMOKE TEST PASSED")
}

func extractIDs(res *mcp.CallToolResult) (agentID, sessionID string) {
	for _, c := range res.Content {
		text, ok := c.(*mcp.TextContent)
		if !ok {
			continue
		}
		agentID = extractFromJSON(text.Text, "agent_id")
		sessionID = extractFromJSON(text.Text, "session_id")
	}
	return
}

func extractFromJSON(jsonStr, key string) string {
	prefix := `"` + key + `":"`
	idx := strings.Index(jsonStr, prefix)
	if idx < 0 {
		return ""
	}
	start := idx + len(prefix)
	end := start
	for end < len(jsonStr) && jsonStr[end] != '"' {
		end++
	}
	return jsonStr[start:end]
}
