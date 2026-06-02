package main

import (
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func main() {
	ensureDirs()

	server := mcp.NewServer(
		&mcp.Implementation{
			Name:    "AgentProbeMCP",
			Version: "0.1.0",
		},
		&mcp.ServerOptions{
			Logger: slog.New(slog.NewTextHandler(os.Stderr, nil)),
		},
	)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "register_probe_agent",
		Description: "Register an agent for the probe test.\n\nReturns immediately with agent details. A server-push notification containing the probe task is dispatched after a short delay.",
	}, handleRegisterProbeAgent)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "write_probe_file",
		Description: "Write the probe result file. Idempotent: duplicate calls return already_done.",
	}, handleWriteProbeFile)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "submit_probe_result",
		Description: "Submit probe result. Idempotent: repeated submits update timestamp only.",
	}, handleSubmitProbeResult)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "generate_probe_report",
		Description: "Generate a Markdown probe compatibility report by scanning outputs and logs.",
	}, handleGenerateProbeReport)

	mcpHandler := mcp.NewStreamableHTTPHandler(func(req *http.Request) *mcp.Server {
		return server
	}, nil)

	// Workaround: Go SDK v1.6.1 requires Accept to contain both
	// application/json and text/event-stream. Some clients (Cursor, Trae)
	// only send application/json. Inject the missing accept type so the
	// SDK handler doesn't reject them with 400.
	handler := http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		accepts := req.Header.Values("Accept")
		hasJSON := false
		hasStream := false
		for _, a := range accepts {
			if strings.Contains(a, "application/json") {
				hasJSON = true
			}
			if strings.Contains(a, "text/event-stream") {
				hasStream = true
			}
		}
		if hasJSON && !hasStream {
			req.Header.Add("Accept", "text/event-stream")
		}
		mcpHandler.ServeHTTP(w, req)
	})

	addr := "127.0.0.1:8799"
	logServer("startup", "host", "127.0.0.1", "port", 8799, "transport", "streamable-http")

	fmt.Println("AgentProbeMCP started")
	fmt.Println("URL: http://127.0.0.1:8799/mcp")
	fmt.Printf("Outputs dir: %s\n", probeOutputsDir)
	fmt.Printf("Logs dir: %s\n", logsDir)

	if err := http.ListenAndServe(addr, handler); err != nil {
		fmt.Fprintf(os.Stderr, "server error: %v\n", err)
		os.Exit(1)
	}
}
