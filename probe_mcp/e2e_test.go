package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func TestEndToEndDebate(t *testing.T) {
	ctx := context.Background()

	// Channels are swapped each phase so stale pushes don't leak.
	var currentPushCh1 chan map[string]any
	var currentPushCh2 chan map[string]any

	client1 := mcp.NewClient(&mcp.Implementation{
		Name:    "test-client-1",
		Version: "1.0.0",
	}, &mcp.ClientOptions{
		LoggingMessageHandler: func(_ context.Context, req *mcp.LoggingMessageRequest) {
			ch := currentPushCh1
			if ch == nil {
				return
			}
			select {
			case ch <- extractPushData(req):
			default:
			}
		},
	})

	client2 := mcp.NewClient(&mcp.Implementation{
		Name:    "test-client-2",
		Version: "1.0.0",
	}, &mcp.ClientOptions{
		LoggingMessageHandler: func(_ context.Context, req *mcp.LoggingMessageRequest) {
			ch := currentPushCh2
			if ch == nil {
				return
			}
			select {
			case ch <- extractPushData(req):
			default:
			}
		},
	})

	transport := &mcp.StreamableClientTransport{
		Endpoint: "http://127.0.0.1:8799/mcp",
	}

	fmt.Println("Connecting clients to MCP server...")
	session1, err := client1.Connect(ctx, transport, nil)
	if err != nil {
		t.Fatalf("Client1 connect failed: %v", err)
	}
	defer session1.Close()

	session2, err := client2.Connect(ctx, transport, nil)
	if err != nil {
		t.Fatalf("Client2 connect failed: %v", err)
	}
	defer session2.Close()

	fmt.Println("Connected.")

	if err := session1.SetLoggingLevel(ctx, &mcp.SetLoggingLevelParams{Level: "info"}); err != nil {
		t.Fatalf("SetLoggingLevel client1 failed: %v", err)
	}
	if err := session2.SetLoggingLevel(ctx, &mcp.SetLoggingLevelParams{Level: "info"}); err != nil {
		t.Fatalf("SetLoggingLevel client2 failed: %v", err)
	}

	// ------------------------------------------------------------------
	// Register both agents
	// ------------------------------------------------------------------
	fmt.Println("\n=== Register Agent 1 ===")
	res1, err := session1.CallTool(ctx, &mcp.CallToolParams{
		Name: "register_agent",
		Arguments: map[string]any{
			"client": "test-client",
			"model":  "test-model-1",
		},
	})
	if err != nil {
		t.Fatalf("register_agent 1 failed: %v", err)
	}
	agentID1, sessionID1 := extractRegisterIDs(res1)
	fmt.Printf("Agent1: agent_id=%s session_id=%s\n", agentID1, sessionID1)

	fmt.Println("\n=== Register Agent 2 ===")
	res2, err := session2.CallTool(ctx, &mcp.CallToolParams{
		Name: "register_agent",
		Arguments: map[string]any{
			"client": "test-client",
			"model":  "test-model-2",
		},
	})
	if err != nil {
		t.Fatalf("register_agent 2 failed: %v", err)
	}
	agentID2, sessionID2 := extractRegisterIDs(res2)
	fmt.Printf("Agent2: agent_id=%s session_id=%s\n", agentID2, sessionID2)

	if sessionID1 != sessionID2 {
		t.Fatalf("Agents not in same session: %s vs %s", sessionID1, sessionID2)
	}
	fmt.Println("Both agents in same session ✓")

	// ------------------------------------------------------------------
	// Start session manually (auto-start disabled)
	// ------------------------------------------------------------------
	fmt.Println("\n=== Start session via admin API ===")
	startBody := fmt.Sprintf(`{"session_id":"%s"}`, sessionID1)
	resp, err := http.Post("http://127.0.0.1:8799/api/start", "application/json", strings.NewReader(startBody))
	if err != nil {
		t.Fatalf("Failed to start session: %v", err)
	}
	resp.Body.Close()
	fmt.Println("Session started via API")

	// ------------------------------------------------------------------
	// Run phases for both agents
	// ------------------------------------------------------------------
	runPhase := func(phase, toolName string, sess *mcp.ClientSession, agID string, pushCh chan map[string]any) {
		fmt.Printf("\n--- Waiting for %s push for %s ---\n", phase, agID)
		var pushData map[string]any
		select {
		case pushData = <-pushCh:
			fmt.Printf("Push received for %s: %+v\n", agID, pushData)
		case <-time.After(35 * time.Second):
			t.Fatalf("Timeout waiting for %s push for %s", phase, agID)
		}

		taskID, _ := pushData["task_id"].(string)
		if taskID == "" {
			t.Fatalf("Push missing task_id for %s (%s)", phase, agID)
		}

		fmt.Printf("--- Submit %s for %s (task=%s) ---\n", toolName, agID, taskID)
		res, err := sess.CallTool(ctx, &mcp.CallToolParams{
			Name: toolName,
			Arguments: map[string]any{
				"agent_id": agID,
				"task_id":  taskID,
				"content": map[string]any{
					"phase": phase,
					"ok":    true,
				},
			},
		})
		if err != nil {
			t.Fatalf("%s failed for %s: %v", toolName, agID, err)
		}
		printResult(res)
	}

	phases := []struct {
		phase string
		tool  string
	}{
		{"proposal", "submit_proposal"},
		{"challenge", "submit_challenge"},
		{"revision", "submit_revision"},
		{"consensus", "submit_consensus"},
	}

	for _, p := range phases {
		fmt.Printf("\n========== Phase: %s ==========\n", p.phase)
		currentPushCh1 = make(chan map[string]any, 10)
		currentPushCh2 = make(chan map[string]any, 10)

		var wg sync.WaitGroup
		wg.Add(2)
		go func() {
			defer wg.Done()
			runPhase(p.phase, p.tool, session1, agentID1, currentPushCh1)
		}()
		go func() {
			defer wg.Done()
			runPhase(p.phase, p.tool, session2, agentID2, currentPushCh2)
		}()
		wg.Wait()
	}

	// ------------------------------------------------------------------
	// Verify session completed
	// ------------------------------------------------------------------
	fmt.Println("\n=== Verify session status ===")
	statusRes, err := session1.CallTool(ctx, &mcp.CallToolParams{
		Name:      "get_runtime_status",
		Arguments: map[string]any{"agent_id": agentID1},
	})
	if err != nil {
		t.Fatalf("get_runtime_status failed: %v", err)
	}
	printResult(statusRes)

	fmt.Println("\n=== Generate report ===")
	repRes, err := session1.CallTool(ctx, &mcp.CallToolParams{
		Name:      "generate_report",
		Arguments: map[string]any{"session_id": sessionID1},
	})
	if err != nil {
		t.Fatalf("generate_report failed: %v", err)
	}
	printResult(repRes)

	// ------------------------------------------------------------------
	// Verify summary.json
	// ------------------------------------------------------------------
	summaryPath := fmt.Sprintf("E:/DesignDocMCPTest1/probe_outputs/%s/summary.json", sessionID1)
	var summary map[string]any
	for i := 0; i < 10; i++ {
		data, err := os.ReadFile(summaryPath)
		if err == nil {
			if err := json.Unmarshal(data, &summary); err == nil {
				break
			}
		}
		time.Sleep(500 * time.Millisecond)
	}
	if summary == nil {
		t.Fatalf("summary.json not found or unreadable: %s", summaryPath)
	}

	result, _ := summary["result"].(string)
	if result != "PASS" && result != "PARTIAL" {
		t.Fatalf("Expected PASS or PARTIAL, got %s", result)
	}
	fmt.Printf("Summary result: %s ✓\n", result)
	fmt.Println("\n=== All tests completed successfully ===")
}

func extractPushData(req *mcp.LoggingMessageRequest) map[string]any {
	params := req.Params
	var pushData map[string]any
	if s, ok := params.Data.(string); ok {
		_ = json.Unmarshal([]byte(s), &pushData)
	} else if b, ok := params.Data.([]byte); ok {
		_ = json.Unmarshal(b, &pushData)
	} else {
		b, _ := json.Marshal(params.Data)
		_ = json.Unmarshal(b, &pushData)
	}
	return pushData
}

func printResult(res *mcp.CallToolResult) {
	for _, c := range res.Content {
		if text, ok := c.(*mcp.TextContent); ok {
			fmt.Println(text.Text)
		} else {
			fmt.Printf("%+v\n", c)
		}
	}
}

func extractRegisterIDs(res *mcp.CallToolResult) (agentID, sessionID string) {
	for _, c := range res.Content {
		text, ok := c.(*mcp.TextContent)
		if !ok {
			continue
		}
		var obj map[string]any
		if err := json.Unmarshal([]byte(text.Text), &obj); err != nil {
			continue
		}
		if v, ok := obj["agent_id"].(string); ok {
			agentID = v
		}
		if v, ok := obj["session_id"].(string); ok {
			sessionID = v
		}
	}
	return
}

func TestMain(m *testing.M) {
	if _, err := os.Stat("mini-debate-runtime.exe"); err == nil {
		fmt.Println("Found mini-debate-runtime.exe – assuming server is running externally.")
	}
	os.Exit(m.Run())
}
