package main

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func TestSmokeGetRuntimeStatus(t *testing.T) {
	ctx := context.Background()

	client := mcp.NewClient(&mcp.Implementation{Name: "smoke-test", Version: "1.0.0"}, nil)
	transport := &mcp.StreamableClientTransport{Endpoint: "http://127.0.0.1:8799/mcp"}

	session, err := client.Connect(ctx, transport, nil)
	if err != nil {
		t.Fatalf("connect failed: %v", err)
	}
	defer session.Close()

	// 1. register_agent
	res1, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name:      "register_agent",
		Arguments: map[string]any{"client": "smoke-client", "model": "smoke-model"},
	})
	if err != nil {
		t.Fatalf("register_agent failed: %v", err)
	}

	var agentID, sessID string
	for _, c := range res1.Content {
		text, ok := c.(*mcp.TextContent)
		if !ok {
			continue
		}
		agentID = extractFromJSON(text.Text, "agent_id")
		sessID = extractFromJSON(text.Text, "session_id")
	}
	if agentID == "" || sessID == "" {
		t.Fatalf("missing ids: agentID=%s sessID=%s", agentID, sessID)
	}
	t.Logf("registered agent_id=%s session_id=%s", agentID, sessID)

	// 2. get_runtime_status (unknown agent)
	res2, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name:      "get_runtime_status",
		Arguments: map[string]any{"agent_id": "nonexistent"},
	})
	if err != nil {
		t.Fatalf("get_runtime_status unknown failed: %v", err)
	}
	for _, c := range res2.Content {
		if text, ok := c.(*mcp.TextContent); ok {
			t.Logf("status unknown: %s", text.Text)
			if !strings.Contains(text.Text, `"registered":false`) {
				t.Fatalf("expected registered=false for unknown agent, got: %s", text.Text)
			}
		}
	}

	// 3. get_runtime_status (known agent)
	res3, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name:      "get_runtime_status",
		Arguments: map[string]any{"agent_id": agentID},
	})
	if err != nil {
		t.Fatalf("get_runtime_status known failed: %v", err)
	}
	for _, c := range res3.Content {
		if text, ok := c.(*mcp.TextContent); ok {
			t.Logf("status known: %s", text.Text)
			if !strings.Contains(text.Text, `"registered":true`) {
				t.Fatalf("expected registered=true, got: %s", text.Text)
			}
			if !strings.Contains(text.Text, `"phase":"REGISTERED"`) && !strings.Contains(text.Text, `"phase":"PROPOSAL"`) {
				t.Fatalf("expected phase REGISTERED or PROPOSAL, got: %s", text.Text)
			}
		}
	}

	// 4. idempotent register - same client+model should return same session
	res4, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name:      "register_agent",
		Arguments: map[string]any{"client": "smoke-client", "model": "smoke-model"},
	})
	if err != nil {
		t.Fatalf("idempotent register failed: %v", err)
	}
	var agentID2, sessID2 string
	for _, c := range res4.Content {
		text, ok := c.(*mcp.TextContent)
		if !ok {
			continue
		}
		agentID2 = extractFromJSON(text.Text, "agent_id")
		sessID2 = extractFromJSON(text.Text, "session_id")
	}
	if agentID2 != agentID || sessID2 != sessID {
		t.Fatalf("idempotency broken: first=%s/%s second=%s/%s", agentID, sessID, agentID2, sessID2)
	}
	t.Logf("idempotency OK: same session returned")

	// 5. Poll until phase advances (should go to PROPOSAL quickly)
	time.Sleep(500 * time.Millisecond)
	res5, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name:      "get_runtime_status",
		Arguments: map[string]any{"agent_id": agentID},
	})
	if err != nil {
		t.Fatalf("poll failed: %v", err)
	}
	for _, c := range res5.Content {
		if text, ok := c.(*mcp.TextContent); ok {
			t.Logf("poll status: %s", text.Text)
			if !strings.Contains(text.Text, `"phase":"PROPOSAL"`) {
				t.Fatalf("expected phase PROPOSAL after poll, got: %s", text.Text)
			}
			if !strings.Contains(text.Text, `"needs_submit":true`) {
				t.Fatalf("expected needs_submit=true, got: %s", text.Text)
			}
		}
	}

	t.Log("SMOKE TEST PASSED")
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
