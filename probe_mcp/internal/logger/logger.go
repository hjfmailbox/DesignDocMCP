package logger

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/fluorine/designdoc-mcp/probe/internal/state"
)

var (
	LogsDir           = filepath.Join(".", "logs")
	ProbeOutputsDir   = `E:\DesignDocMCPTest1\probe_outputs`
	PingValidationDir = filepath.Join(ProbeOutputsDir, "ping_validation")

	logMu sync.Mutex
)

func EnsureDirs() {
	_ = os.MkdirAll(LogsDir, 0755)
	_ = os.MkdirAll(ProbeOutputsDir, 0755)
	_ = os.MkdirAll(PingValidationDir, 0755)
}

func writeJSONL(filename string, record map[string]any) {
	logMu.Lock()
	defer logMu.Unlock()

	record["ts"] = time.Now().UTC().Format(time.RFC3339Nano)
	data, _ := json.Marshal(record)

	f, err := os.OpenFile(filepath.Join(LogsDir, filename), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return
	}
	defer f.Close()

	_, _ = fmt.Fprintln(f, string(data))
}

func LogTimeline(sessionID, event, phase, taskID string) {
	rec := map[string]any{
		"session_id": sessionID,
		"event":      event,
		"phase":      phase,
	}
	if taskID != "" {
		rec["task_id"] = taskID
	}
	writeJSONL("session_timeline.jsonl", rec)
}

func LogPush(sessionID, phase, taskID string, retry int) {
	rec := map[string]any{
		"session_id": sessionID,
		"event":      "push",
		"phase":      phase,
		"task_id":    taskID,
		"retry":      retry,
	}
	writeJSONL("pushes.jsonl", rec)
}

func LogResponse(sessionID, phase, taskID, agentID, status string) {
	rec := map[string]any{
		"session_id": sessionID,
		"event":      "response",
		"phase":      phase,
		"task_id":    taskID,
		"agent_id":   agentID,
		"status":     status,
	}
	writeJSONL("responses.jsonl", rec)
}

func LogEvent(sessionID, event string, fields map[string]any) {
	rec := map[string]any{
		"session_id": sessionID,
		"event":      event,
	}
	for k, v := range fields {
		rec[k] = v
	}
	writeJSONL("session_timeline.jsonl", rec)
}

func LogReport(sessionID string, report map[string]any) {
	report["ts"] = time.Now().UTC().Format(time.RFC3339Nano)
	report["session_id"] = sessionID

	data, _ := json.MarshalIndent(report, "", "  ")

	_ = os.MkdirAll(filepath.Join(ProbeOutputsDir, sessionID), 0755)
	_ = os.WriteFile(filepath.Join(ProbeOutputsDir, sessionID, "report.json"), data, 0644)
}

// ---------------------------------------------------------------------------
// Observability logging
// ---------------------------------------------------------------------------

func LogNotificationSent(sessionID, agentID, agentName, phase, taskID, method string, payload map[string]any) {
	rec := map[string]any{
		"type":       "NOTIFICATION_SENT",
		"timestamp":  time.Now().UTC().Format(time.RFC3339Nano),
		"session_id": sessionID,
		"agent_id":   agentID,
		"agent_name": agentName,
		"phase":      phase,
		"task_id":    taskID,
		"method":     method,
		"payload":    payload,
	}
	writeJSONL("notifications.jsonl", rec)
}

func LogClientEvent(agentID, agentName, event, connID string) {
	rec := map[string]any{
		"type":          "CONNECTION_EVENT",
		"timestamp":     time.Now().UTC().Format(time.RFC3339Nano),
		"agent_id":      agentID,
		"agent_name":    agentName,
		"event":         event,
		"connection_id": connID,
	}
	writeJSONL("connections.jsonl", rec)
}

func LogPingSent(sessionID, agentID, pingID string) {
	rec := map[string]any{
		"type":      "PING_SENT",
		"timestamp": time.Now().UTC().Format(time.RFC3339Nano),
		"session_id": sessionID,
		"agent_id":  agentID,
		"ping_id":   pingID,
	}
	writeJSONL("pings.jsonl", rec)
}

func WriteConnectedClients(agents []*state.Agent) {
	clients := make(map[string]map[string]any)
	for _, a := range agents {
		clients[a.AgentID] = map[string]any{
			"connected":     a.IsConnected(),
			"last_seen":     a.LastSeen.UTC().Format(time.RFC3339Nano),
			"connection_id": a.ConnectionID,
			"display_name":  a.DisplayName,
			"status":        a.GetStatus(),
		}
	}
	data, _ := json.MarshalIndent(clients, "", "  ")
	logMu.Lock()
	defer logMu.Unlock()
	_ = os.WriteFile(filepath.Join(LogsDir, "connected_clients.json"), data, 0644)
}

func WritePingResponse(agentID, pingID string, responded bool) {
	rec := map[string]any{
		"type":      "PING_RESPONSE",
		"timestamp": time.Now().UTC().Format(time.RFC3339Nano),
		"agent_id":  agentID,
		"ping_id":   pingID,
		"responded": responded,
	}
	writeJSONL("ping_responses.jsonl", rec)
}

func WriteSessionReport(s *state.MultiAgentSession, result string) {
	sessionDir := filepath.Join(ProbeOutputsDir, s.SessionID)
	_ = os.MkdirAll(sessionDir, 0755)

	agentList := make([]map[string]any, 0)
	for _, a := range s.GetAgents() {
		agentList = append(agentList, map[string]any{
			"agent_id":     a.AgentID,
			"display_name": a.DisplayName,
			"client":       a.Client,
			"model":        a.Model,
			"status":       a.GetStatus(),
		})
	}

	report := map[string]any{
		"session_id": s.SessionID,
		"result":     result,
		"agents":     agentList,
		"phases":     s.CompletedPhases,
		"completed":  s.IsComplete(),
		"ts":         time.Now().UTC().Format(time.RFC3339Nano),
	}

	data, _ := json.MarshalIndent(report, "", "  ")
	_ = os.WriteFile(filepath.Join(sessionDir, "summary.json"), data, 0644)

	// Write per-session timeline copy.
	_ = os.WriteFile(filepath.Join(sessionDir, "timeline.jsonl"), []byte{}, 0644)
}
