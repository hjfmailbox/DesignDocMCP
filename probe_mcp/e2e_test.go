package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"sync"
	"testing"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func TestEndToEndDebate(t *testing.T) {
	ctx := context.Background()

	pushReceived := make(chan map[string]any, 1)
	var pushOnce sync.Once

	client := mcp.NewClient(&mcp.Implementation{
		Name:    "debate-test-client",
		Version: "1.0.0",
	}, &mcp.ClientOptions{
		LoggingMessageHandler: func(_ context.Context, req *mcp.LoggingMessageRequest) {
			params := req.Params
			fmt.Printf("[PUSH RECEIVED] level=%s logger=%s data=%v\n", params.Level, params.Logger, params.Data)
			var pushData map[string]any
			if s, ok := params.Data.(string); ok {
				_ = json.Unmarshal([]byte(s), &pushData)
			} else if b, ok := params.Data.([]byte); ok {
				_ = json.Unmarshal(b, &pushData)
			} else {
				b, _ := json.Marshal(params.Data)
				_ = json.Unmarshal(b, &pushData)
			}
			pushOnce.Do(func() { pushReceived <- pushData })
		},
	})

	transport := &mcp.StreamableClientTransport{
		Endpoint: "http://127.0.0.1:8799/mcp",
	}

	fmt.Println("Connecting to MCP server at http://127.0.0.1:8799/mcp ...")
	session, err := client.Connect(ctx, transport, nil)
	if err != nil {
		t.Fatalf("Connect failed: %v", err)
	}
	defer session.Close()
	fmt.Println("Connected.")

	fmt.Println("Setting logging level to info ...")
	if err := session.SetLoggingLevel(ctx, &mcp.SetLoggingLevelParams{Level: "info"}); err != nil {
		t.Fatalf("SetLoggingLevel failed: %v", err)
	}
	fmt.Println("Logging level set.")

	// 1. register_agent
	fmt.Println("\n=== 1. register_agent ===")
	res1, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name: "register_agent",
		Arguments: map[string]any{
			"client": "test-client",
			"model":  "test-model",
		},
	})
	if err != nil {
		t.Fatalf("register_agent failed: %v", err)
	}
	printResult(res1)

	agentID, sessionID := extractRegisterIDs(res1)
	if agentID == "" || sessionID == "" {
		t.Fatal("Could not extract agent_id/session_id from register result")
	}
	fmt.Printf("Using agent_id=%s session_id=%s\n", agentID, sessionID)

	// Helper to wait for push and respond
	runPhase := func(phase, toolName string) {
		fmt.Printf("\n=== Waiting for %s push (max 35s) ===\n", phase)
		var pushData map[string]any
		select {
		case pushData = <-pushReceived:
			fmt.Printf("Push received: %+v\n", pushData)
		case <-time.After(35 * time.Second):
			t.Fatalf("Timeout waiting for %s push", phase)
		}

		taskID, _ := pushData["task_id"].(string)
		if taskID == "" {
			t.Fatalf("Push missing task_id for %s", phase)
		}

		// Reset for next phase
		pushOnce = sync.Once{}
		pushReceived = make(chan map[string]any, 1)

		fmt.Printf("\n=== Submit %s (task_id=%s) ===\n", toolName, taskID)
		res, err := session.CallTool(ctx, &mcp.CallToolParams{
			Name: toolName,
			Arguments: map[string]any{
				"agent_id": agentID,
				"task_id":  taskID,
				"content": map[string]any{
					"phase": phase,
					"ok":    true,
				},
			},
		})
		if err != nil {
			t.Fatalf("%s failed: %v", toolName, err)
		}
		printResult(res)
	}

	// Phase 2: PROPOSAL
	runPhase("proposal", "submit_proposal")

	// Phase 3: CHALLENGE
	runPhase("challenge", "submit_challenge")

	// Phase 4: REVISION
	runPhase("revision", "submit_revision")

	// Phase 5: CONSENSUS
	runPhase("consensus", "submit_consensus")

	// 6. generate_report
	fmt.Println("\n=== 6. generate_report ===")
	res6, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name:      "generate_report",
		Arguments: map[string]any{"session_id": sessionID},
	})
	if err != nil {
		t.Fatalf("generate_report failed: %v", err)
	}
	printResult(res6)

	// 7. Verify report file exists
	reportPath := fmt.Sprintf("E:/DesignDocMCPTest1/probe_outputs/%s/report.json", sessionID)
	if _, err := os.Stat(reportPath); os.IsNotExist(err) {
		t.Fatalf("Report file not found: %s", reportPath)
	}
	fmt.Printf("Report file exists: %s\n", reportPath)

	data, _ := os.ReadFile(reportPath)
	var report map[string]any
	if err := json.Unmarshal(data, &report); err != nil {
		t.Fatalf("Failed to parse report: %v", err)
	}
	if report["result"] != "PASS" {
		t.Fatalf("Expected result PASS, got %v", report["result"])
	}
	fmt.Println("Report result: PASS")

	fmt.Println("\n=== All tests completed successfully ===")
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
	if _, err := os.Stat("probe_mcp.exe"); err == nil {
		fmt.Println("Found probe_mcp.exe – assuming server is running externally.")
	}
	os.Exit(m.Run())
}
