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
			Name:    "MiniDebateRuntime",
			Version: "0.2.0",
		},
		&mcp.ServerOptions{
			Logger: slog.New(slog.NewTextHandler(os.Stderr, nil)),
		},
	)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "register_agent",
		Description: "Register an agent for the mini-debate runtime.\n\nReturns session details. A server-push phase loop begins immediately after registration.",
	}, handleRegisterAgent)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "submit_proposal",
		Description: "Submit a proposal response for the current PROPOSAL phase. Idempotent per task_id.",
	}, handleSubmitProposal)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "submit_challenge",
		Description: "Submit a challenge response for the current CHALLENGE phase. Idempotent per task_id.",
	}, handleSubmitChallenge)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "submit_revision",
		Description: "Submit a revision response for the current REVISION phase. Idempotent per task_id.",
	}, handleSubmitRevision)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "submit_consensus",
		Description: "Submit a consensus vote for the current CONSENSUS phase. Idempotent per task_id.",
	}, handleSubmitConsensus)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "generate_report",
		Description: "Generate a Markdown debate runtime report by scanning sessions and logs.",
	}, handleGenerateReport)

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
	logTimeline("", "startup", "", "")

	fmt.Println("MiniDebateRuntime started")
	fmt.Println("URL: http://127.0.0.1:8799/mcp")
	fmt.Printf("Outputs dir: %s\n", probeOutputsDir)
	fmt.Printf("Logs dir: %s\n", logsDir)

	if err := http.ListenAndServe(addr, handler); err != nil {
		fmt.Fprintf(os.Stderr, "server error: %v\n", err)
		os.Exit(1)
	}
}
