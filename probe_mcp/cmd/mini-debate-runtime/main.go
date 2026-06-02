package main

import (
	"context"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/fluorine/designdoc-mcp/probe/internal/api"
	"github.com/fluorine/designdoc-mcp/probe/internal/logger"
	"github.com/fluorine/designdoc-mcp/probe/internal/orchestrator"
	"github.com/fluorine/designdoc-mcp/probe/internal/scheduler"
	"github.com/fluorine/designdoc-mcp/probe/internal/server"
	"github.com/fluorine/designdoc-mcp/probe/internal/state"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func main() {
	mode := flag.String("mode", "server", "Run mode: server or orchestrator")
	sessionID := flag.String("session", "", "Session ID to orchestrate (orchestrator mode only)")
	spawnerFlag := flag.String("spawner", "mock", "Spawner type: mock or cli (orchestrator mode only)")
	delaySec := flag.Int("delay", 0, "Seconds to wait before starting orchestration (allows agents to register)")
	flag.Parse()

	logger.EnsureDirs()

	// ------------------------------------------------------------------
	// MCP server setup (shared by both modes)
	// ------------------------------------------------------------------
	mcpServer := mcp.NewServer(
		&mcp.Implementation{
			Name:    "MiniDebateRuntime",
			Version: "0.2.0",
		},
		&mcp.ServerOptions{
			Logger: slog.New(slog.NewTextHandler(os.Stderr, nil)),
		},
	)

	mcp.AddTool(mcpServer, &mcp.Tool{
		Name:        "register_agent",
		Description: "Register an agent for the mini-debate runtime.\n\nReturns session details. A server-push phase loop begins immediately after registration.",
	}, server.HandleRegisterAgent)

	mcp.AddTool(mcpServer, &mcp.Tool{
		Name:        "submit_proposal",
		Description: "Submit a proposal response for the current PROPOSAL phase. Idempotent per task_id.",
	}, server.HandleSubmitProposal)

	mcp.AddTool(mcpServer, &mcp.Tool{
		Name:        "submit_challenge",
		Description: "Submit a challenge response for the current CHALLENGE phase. Idempotent per task_id.",
	}, server.HandleSubmitChallenge)

	mcp.AddTool(mcpServer, &mcp.Tool{
		Name:        "submit_revision",
		Description: "Submit a revision response for the current REVISION phase. Idempotent per task_id.",
	}, server.HandleSubmitRevision)

	mcp.AddTool(mcpServer, &mcp.Tool{
		Name:        "submit_consensus",
		Description: "Submit a consensus vote for the current CONSENSUS phase. Idempotent per task_id.",
	}, server.HandleSubmitConsensus)

	mcp.AddTool(mcpServer, &mcp.Tool{
		Name:        "get_runtime_status",
		Description: "Query current session status for the given agent. Returns phase, task_id, and whether a submit is needed.",
	}, server.HandleGetRuntimeStatus)

	mcp.AddTool(mcpServer, &mcp.Tool{
		Name:        "generate_report",
		Description: "Generate a Markdown debate runtime report by scanning sessions and logs.",
	}, server.HandleGenerateReport)

	mcpHandler := mcp.NewStreamableHTTPHandler(func(req *http.Request) *mcp.Server {
		return mcpServer
	}, nil)

	// Workaround: Go SDK v1.6.1 requires Accept to contain both
	// application/json and text/event-stream. Some clients (Cursor, Trae)
	// only send application/json. Inject the missing accept type so the
	// SDK handler doesn't reject them with 400.
	mcpWithAccept := http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
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

	handler := api.AdminMux(mcpWithAccept)

	addr := "127.0.0.1:8799"
	logger.LogTimeline("", "startup", "", "")

	// ------------------------------------------------------------------
	// Mode-specific setup
	// ------------------------------------------------------------------
	if *mode == "orchestrator" {
		var spawner orchestrator.Spawner
		switch *spawnerFlag {
		case "cli":
			spawner = &orchestrator.CLISpawner{}
		case "mock":
			spawner = &orchestrator.MockSpawner{}
		default:
			fmt.Fprintf(os.Stderr, "unknown spawner %q, use mock or cli\n", *spawnerFlag)
			os.Exit(1)
		}

		orch := &orchestrator.Orchestrator{
			Spawner:  spawner,
			Observer: &orchestrator.BarrierObserver{},
		}

		// Start orchestrator in a goroutine so the HTTP server can accept
		// connections from spawned agent processes.
		go func() {
			if *delaySec > 0 {
				fmt.Printf("Orchestrator waiting %ds for agents to register...\n", *delaySec)
				time.Sleep(time.Duration(*delaySec) * time.Second)
			}

			// Auto-discover session if not provided (or "auto").
			sid := *sessionID
			if sid == "" || sid == "auto" {
				for {
					sessions := state.GetActiveSessions()
					if len(sessions) > 0 {
						sid = sessions[0].SessionID
						fmt.Printf("Auto-discovered session: %s\n", sid)
						break
					}
					fmt.Println("Waiting for session...")
					time.Sleep(2 * time.Second)
				}
			}

			fmt.Printf("Orchestrator starting session %s...\n", sid)
			if err := orch.RunSession(sid); err != nil {
				fmt.Fprintf(os.Stderr, "orchestrator failed: %v\n", err)
			} else {
				fmt.Println("Orchestrator finished session successfully.")
			}
		}()
	} else {
		scheduler.StartScheduler()
		fmt.Println("Scheduler started")
	}

	fmt.Println("MiniDebateRuntime started")
	fmt.Println("MCP Endpoint: http://127.0.0.1:8799/mcp")
	fmt.Println("Admin UI:     http://127.0.0.1:8799/ui")
	fmt.Printf("Outputs dir:  %s\n", logger.ProbeOutputsDir)
	fmt.Printf("Logs dir:     %s\n", logger.LogsDir)

	srv := &http.Server{Addr: addr, Handler: handler}

	// Graceful shutdown on SIGINT / SIGTERM.
	go func() {
		sigCh := make(chan os.Signal, 1)
		signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
		<-sigCh

		fmt.Println("\nShutting down gracefully...")
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := srv.Shutdown(ctx); err != nil {
			fmt.Fprintf(os.Stderr, "shutdown error: %v\n", err)
		}
	}()

	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		fmt.Fprintf(os.Stderr, "server error: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("Server stopped.")
}
