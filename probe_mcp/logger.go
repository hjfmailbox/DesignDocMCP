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

func logServer(event string, kv ...any) {
	rec := map[string]any{"event": event}
	for i := 0; i+1 < len(kv); i += 2 {
		if k, ok := kv[i].(string); ok {
			rec[k] = kv[i+1]
		}
	}
	writeJSONL("server.log", rec)
}

func logProbe(event string, kv ...any) {
	rec := map[string]any{"event": event}
	for i := 0; i+1 < len(kv); i += 2 {
		if k, ok := kv[i].(string); ok {
			rec[k] = kv[i+1]
		}
	}
	writeJSONL("probe_events.log", rec)
}

func logAgentResponse(agentID, probeID, status string, detail map[string]any) {
	rec := map[string]any{
		"agent_id": agentID,
		"probe_id": probeID,
		"status":   status,
		"detail":   detail,
	}
	writeJSONL("agent_response.log", rec)
}
