package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

var (
	logsDir         = filepath.Join(".", "logs")
	probeOutputsDir = `E:\DesignDocMCPTest1\probe_outputs`

	logMu sync.Mutex
)

func ensureDirs() {
	_ = os.MkdirAll(logsDir, 0755)
	_ = os.MkdirAll(probeOutputsDir, 0755)
}

func writeJSONL(filename string, record map[string]any) {
	logMu.Lock()
	defer logMu.Unlock()

	record["ts"] = time.Now().UTC().Format(time.RFC3339Nano)
	data, _ := json.Marshal(record)

	f, err := os.OpenFile(filepath.Join(logsDir, filename), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return
	}
	defer f.Close()

	_, _ = fmt.Fprintln(f, string(data))
}

func logTimeline(sessionID, event, phase, taskID string) {
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

func logPush(sessionID, phase, taskID string, retry int) {
	rec := map[string]any{
		"session_id": sessionID,
		"event":      "push",
		"phase":      phase,
		"task_id":    taskID,
		"retry":      retry,
	}
	writeJSONL("pushes.jsonl", rec)
}

func logResponse(sessionID, phase, taskID, agentID, status string) {
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

func logReport(sessionID string, report map[string]any) {
	report["ts"] = time.Now().UTC().Format(time.RFC3339Nano)
	report["session_id"] = sessionID

	data, _ := json.MarshalIndent(report, "", "  ")

	_ = os.MkdirAll(filepath.Join(probeOutputsDir, sessionID), 0755)
	_ = os.WriteFile(filepath.Join(probeOutputsDir, sessionID, "report.json"), data, 0644)
}
