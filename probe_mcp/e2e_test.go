package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func TestEndToEndProbe(t *testing.T) {
	ctx := context.Background()

	pushReceived := make(chan *mcp.LoggingMessageParams, 1)
	var pushOnce sync.Once

	client := mcp.NewClient(&mcp.Implementation{
		Name:    "probe-test-client",
		Version: "1.0.0",
	}, &mcp.ClientOptions{
		LoggingMessageHandler: func(_ context.Context, req *mcp.LoggingMessageRequest) {
			params := req.Params
			fmt.Printf("[PUSH RECEIVED] level=%s logger=%s data=%v\n", params.Level, params.Logger, params.Data)
			pushOnce.Do(func() { pushReceived <- params })
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

	// 1. register_probe_agent
	fmt.Println("\n=== 1. register_probe_agent ===")
	res1, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name: "register_probe_agent",
		Arguments: map[string]any{
			"agent_name": "TestAgent",
		},
	})
	if err != nil {
		t.Fatalf("register_probe_agent failed: %v", err)
	}
	printResult(res1)

	// Wait for push
	fmt.Println("Waiting for server push notification (max 10s) ...")
	select {
	case p := <-pushReceived:
		fmt.Printf("Push received within timeout: %+v\n", p)
	case <-time.After(10 * time.Second):
		fmt.Println("WARNING: No push notification received within 10s")
	}

	// Extract agent_id and probe_id from result
	agentID, probeID := extractIDs(res1)
	if agentID == "" || probeID == "" {
		t.Fatal("Could not extract agent_id/probe_id from register result")
	}
	fmt.Printf("Using agent_id=%s probe_id=%s\n", agentID, probeID)

	// 2. write_probe_file
	fmt.Println("\n=== 2. write_probe_file ===")
	res2, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name: "write_probe_file",
		Arguments: map[string]any{
			"agent_id": agentID,
			"probe_id": probeID,
			"content": map[string]any{
				"test_field": "hello_from_probe",
			},
		},
	})
	if err != nil {
		t.Fatalf("write_probe_file failed: %v", err)
	}
	printResult(res2)

	// 3. write_probe_file again (idempotency test)
	fmt.Println("\n=== 3. write_probe_file (duplicate / idempotency) ===")
	res3, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name: "write_probe_file",
		Arguments: map[string]any{
			"agent_id": agentID,
			"probe_id": probeID,
			"content": map[string]any{
				"test_field": "should_be_ignored",
			},
		},
	})
	if err != nil {
		t.Fatalf("write_probe_file duplicate failed: %v", err)
	}
	body3 := resultString(res3)
	if !strings.Contains(body3, "already_done") {
		t.Fatalf("Expected idempotency 'already_done', got: %s", body3)
	}
	printResult(res3)

	// 4. submit_probe_result
	fmt.Println("\n=== 4. submit_probe_result ===")
	res4, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name: "submit_probe_result",
		Arguments: map[string]any{
			"agent_id": agentID,
			"probe_id": probeID,
			"result": map[string]any{
				"status": "ok",
				"score": 99,
			},
		},
	})
	if err != nil {
		t.Fatalf("submit_probe_result failed: %v", err)
	}
	printResult(res4)

	// 5. submit_probe_result again (idempotency test)
	fmt.Println("\n=== 5. submit_probe_result (duplicate / idempotency) ===")
	res5, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name: "submit_probe_result",
		Arguments: map[string]any{
			"agent_id": agentID,
			"probe_id": probeID,
			"result": map[string]any{
				"status": "ok",
				"score": 42,
			},
		},
	})
	if err != nil {
		t.Fatalf("submit_probe_result duplicate failed: %v", err)
	}
	body5 := resultString(res5)
	if !strings.Contains(body5, "already_recorded") {
		t.Fatalf("Expected idempotency 'already_recorded', got: %s", body5)
	}
	printResult(res5)

	// 6. generate_probe_report
	fmt.Println("\n=== 6. generate_probe_report ===")
	res6, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name:      "generate_probe_report",
		Arguments: map[string]any{},
	})
	if err != nil {
		t.Fatalf("generate_probe_report failed: %v", err)
	}
	printResult(res6)

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

func resultString(res *mcp.CallToolResult) string {
	var parts []string
	for _, c := range res.Content {
		if text, ok := c.(*mcp.TextContent); ok {
			parts = append(parts, text.Text)
		}
	}
	return strings.Join(parts, "\n")
}

func extractIDs(res *mcp.CallToolResult) (agentID, probeID string) {
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
		if v, ok := obj["probe_id"].(string); ok {
			probeID = v
		}
	}
	return
}

func TestMain(m *testing.M) {
	// Ensure server is running
	if _, err := os.Stat("probe_mcp.exe"); err == nil {
		fmt.Println("Found probe_mcp.exe – assuming server is running externally.")
	}
	os.Exit(m.Run())
}
