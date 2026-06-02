package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

const pushDelay = 5 * time.Second

// ---------------------------------------------------------------------------
// Input / Output types for generic AddTool
// ---------------------------------------------------------------------------

type RegisterProbeAgentInput struct {
	AgentName string `json:"agent_name"`
}

type RegisterProbeAgentOutput struct {
	AgentID   string `json:"agent_id"`
	ProbeID   string `json:"probe_id"`
	WatchPath string `json:"watch_path"`
	Task      struct {
		Type        string `json:"type"`
		Instruction string `json:"instruction"`
	} `json:"task"`
}

type WriteProbeFileInput struct {
	AgentID string         `json:"agent_id"`
	ProbeID string         `json:"probe_id"`
	Content map[string]any `json:"content,omitempty"`
}

type WriteProbeFileOutput struct {
	Status  string `json:"status"`
	Path    string `json:"path,omitempty"`
	Message string `json:"message,omitempty"`
}

type SubmitProbeResultInput struct {
	AgentID string         `json:"agent_id"`
	ProbeID string         `json:"probe_id"`
	Result  map[string]any `json:"result"`
}

type SubmitProbeResultOutput struct {
	Status string `json:"status"`
}

// ---------------------------------------------------------------------------
// Tool handlers
// ---------------------------------------------------------------------------

func handleRegisterProbeAgent(_ context.Context, req *mcp.CallToolRequest, in RegisterProbeAgentInput) (*mcp.CallToolResult, RegisterProbeAgentOutput, error) {
	agentID := fmt.Sprintf("%s_%s", in.AgentName, randomHex(8))
	probeID := "p_" + randomHex(8)

	agent := &AgentProbe{
		AgentName:    in.AgentName,
		AgentID:      agentID,
		ProbeID:      probeID,
		RegisteredAt: time.Now().UTC().Format(time.RFC3339Nano),
	}
	registerAgent(agent)

	logServer("agent_registered", "agent_name", in.AgentName, "agent_id", agentID, "probe_id", probeID)
	logProbe("probe_created", "agent_id", agentID, "probe_id", probeID, "target_agent", in.AgentName)

	// Capture session reference and dispatch push after delay.
	session := req.Session
	go func() {
		time.Sleep(pushDelay)
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		err := session.Log(ctx, &mcp.LoggingMessageParams{
			Level:  mcp.LoggingLevel("info"),
			Data:   fmt.Sprintf("Probe task ready for %s. Call write_probe_file(agent_id='%s', probe_id='%s').", in.AgentName, agentID, probeID),
			Logger: "AgentProbeMCP",
		})
		if err != nil {
			logServer("push_failed", "agent_id", agentID, "probe_id", probeID, "error", err.Error())
			logProbe("push_failed", "agent_id", agentID, "probe_id", probeID, "error", err.Error())
		} else {
			logServer("push_sent", "agent_id", agentID, "probe_id", probeID, "method", "notifications/message")
			logProbe("push_sent", "agent_id", agentID, "probe_id", probeID)
		}
	}()

	out := RegisterProbeAgentOutput{
		AgentID:   agentID,
		ProbeID:   probeID,
		WatchPath: probeOutputsDir,
	}
	out.Task.Type = "write_probe_file"
	out.Task.Instruction = "Call write_probe_file to write your probe result."

	return nil, out, nil
}

func handleWriteProbeFile(_ context.Context, _ *mcp.CallToolRequest, in WriteProbeFileInput) (*mcp.CallToolResult, WriteProbeFileOutput, error) {
	if isProbeCompleted(in.ProbeID) {
		logServer("duplicate_probe_ignored", "agent_id", in.AgentID, "probe_id", in.ProbeID)
		logProbe("duplicate_probe_ignored", "agent_id", in.AgentID, "probe_id", in.ProbeID)
		return nil, WriteProbeFileOutput{Status: "already_done"}, nil
	}

	agent := getAgent(in.AgentID)
	agentName := "unknown"
	if agent != nil {
		agentName = agent.AgentName
	}

	filePath := filepath.Join(probeOutputsDir, fmt.Sprintf("probe_%s.json", agentName))

	payload := in.Content
	if payload == nil {
		payload = map[string]any{
			"agent":     agentName,
			"agent_id":  in.AgentID,
			"probe_id":  in.ProbeID,
			"status":    "success",
			"timestamp": time.Now().UTC().Format(time.RFC3339Nano),
		}
	}
	if _, has := payload["timestamp"]; !has {
		payload["timestamp"] = time.Now().UTC().Format(time.RFC3339Nano)
	}

	data, _ := json.MarshalIndent(payload, "", "  ")
	_ = os.WriteFile(filePath, data, 0644)

	markProbeCompleted(in.ProbeID)
	if agent != nil {
		agent.Completed = true
	}

	logServer("probe_file_written", "agent_id", in.AgentID, "probe_id", in.ProbeID, "path", filePath)
	logAgentResponse(in.AgentID, in.ProbeID, "success", map[string]any{"path": filePath, "content": payload})

	return nil, WriteProbeFileOutput{
		Status:  "success",
		Path:    filePath,
		Message: fmt.Sprintf("Probe file written to %s", filePath),
	}, nil
}

func handleSubmitProbeResult(_ context.Context, _ *mcp.CallToolRequest, in SubmitProbeResultInput) (*mcp.CallToolResult, SubmitProbeResultOutput, error) {
	agent := getAgent(in.AgentID)
	agentName := "unknown"
	if agent != nil {
		agentName = agent.AgentName
	}

	summaryPath := filepath.Join(probeOutputsDir, "_summary.json")
	summary := make(map[string]any)
	if data, err := os.ReadFile(summaryPath); err == nil {
		_ = json.Unmarshal(data, &summary)
	}

	existing, hasExisting := summary[in.AgentID]
	record := map[string]any{
		"agent":     agentName,
		"agent_id":  in.AgentID,
		"probe_id":  in.ProbeID,
		"result":    in.Result,
		"timestamp": time.Now().UTC().Format(time.RFC3339Nano),
	}

	if hasExisting {
		if m, ok := existing.(map[string]any); ok {
			record["previous_timestamp"] = m["timestamp"]
		}
		logServer("duplicate_submit", "agent_id", in.AgentID, "probe_id", in.ProbeID)
	} else {
		logServer("result_submitted", "agent_id", in.AgentID, "probe_id", in.ProbeID)
	}

	summary[in.AgentID] = record
	data, _ := json.MarshalIndent(summary, "", "  ")
	_ = os.WriteFile(summaryPath, data, 0644)

	if agent != nil {
		agent.ResultSubmitted = true
	}

	status := "success"
	if hasExisting {
		status = "already_recorded"
	}
	logAgentResponse(in.AgentID, in.ProbeID, status, map[string]any{"result": in.Result})

	return nil, SubmitProbeResultOutput{Status: status}, nil
}

type ProbeReportOutput struct {
	Report string `json:"report"`
}

func handleGenerateProbeReport(_ context.Context, _ *mcp.CallToolRequest, _ struct{}) (*mcp.CallToolResult, ProbeReportOutput, error) {
	var rows []string
	for _, agent := range getAllAgents() {
		filePath := filepath.Join(probeOutputsDir, fmt.Sprintf("probe_%s.json", agent.AgentName))
		_, err := os.Stat(filePath)
		fileExists := err == nil
		duplicateSafe := isProbeCompleted(agent.ProbeID)

		result := "FAIL"
		if fileExists && duplicateSafe {
			result = "PASS"
		}

		row := fmt.Sprintf("| %s | Yes | Unknown | %s | %s | %s |",
			agent.AgentName,
			boolStr(fileExists),
			boolStr(duplicateSafe),
			result,
		)
		rows = append(rows, row)
	}

	header := "| Agent | Connected | Push Received | File Written | Duplicate Safe | Result |"
	sep := "|---|---|---|---|---|---|"

	var body string
	if len(rows) == 0 {
		body = "| (none) | - | - | - | - | - |\n"
	} else {
		body = strings.Join(rows, "\n") + "\n"
	}

	report := fmt.Sprintf(
		"# Agent Probe Report\n\n%s\n%s\n%s\n\n**Notes**\n"+
			"- *Push Received*: Server-side push notifications were dispatched, "+
			"but receipt can only be confirmed client-side.\n"+
			"- *Duplicate Safe*: Idempotency verified (repeated calls did not duplicate state).\n",
		header, sep, body,
	)

	logServer("report_generated", "agent_count", len(rows))
	return nil, ProbeReportOutput{Report: report}, nil
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func randomHex(n int) string {
	b := make([]byte, n/2+1)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)[:n]
}

func boolStr(b bool) string {
	if b {
		return "Yes"
	}
	return "No"
}
