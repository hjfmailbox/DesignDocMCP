// DesignDoc MCP Gateway — Go-based MCP transport layer that proxies to Python Engine API.
package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net/http"
	"time"

	mcptools "github.com/fluorine/designdoc-mcp-gateway/internal/mcp"
	"github.com/fluorine/designdoc-mcp-gateway/internal/proxy"
	sdkmcp "github.com/modelcontextprotocol/go-sdk/mcp"
)

func main() {
	var (
		transport   = flag.String("transport", "stdio", "Transport type: stdio | streamable-http")
		host        = flag.String("host", "127.0.0.1", "Host to listen on (streamable-http)")
		port        = flag.Int("port", 8765, "Port to listen on (streamable-http)")
		apiBaseURL  = flag.String("api-base-url", "http://127.0.0.1:9000", "Python Engine API base URL")
		healthRetry = flag.Int("health-retry", 30, "Max seconds to wait for Python API to become ready")
	)
	flag.Parse()

	pc := proxy.NewClient(*apiBaseURL)

	// Wait for Python API to be reachable.
	log.Printf("Waiting for Python API at %s ...", *apiBaseURL)
	if err := waitForAPI(context.Background(), pc, *healthRetry); err != nil {
		log.Fatalf("Python API not available: %v", err)
	}
	log.Println("Python API is ready.")

	// Create MCP server.
	server := sdkmcp.NewServer(
		&sdkmcp.Implementation{
			Name:    "designdoc-mcp-gateway",
			Version: "0.4.0",
		},
		nil,
	)

	// Register all tools.
	mcptools.RegisterAllTools(server, pc)
	log.Println("All tools registered.")

	switch *transport {
	case "stdio":
		log.Println("Starting MCP server on stdio...")
		if err := server.Run(context.Background(), &sdkmcp.StdioTransport{}); err != nil {
			log.Fatalf("stdio server error: %v", err)
		}

	case "streamable-http":
		addr := fmt.Sprintf("%s:%d", *host, *port)

		// Support both SSE and streamable-http on the same port,
		// matching the old FastMCP server behavior.
		mux := http.NewServeMux()

		// SSE transport at /sse and /mcp/sse (legacy client compatibility)
		sseHandler := sdkmcp.NewSSEHandler(func(req *http.Request) *sdkmcp.Server {
			return server
		}, nil)
		mux.Handle("/sse", sseHandler)
		mux.Handle("/mcp/sse", sseHandler)

		// Streamable-http transport at / and /mcp
		streamableHandler := sdkmcp.NewStreamableHTTPHandler(func(req *http.Request) *sdkmcp.Server {
			return server
		}, nil)
		mux.Handle("/", streamableHandler)
		mux.Handle("/mcp", streamableHandler)

		log.Printf("Starting MCP server on streamable-http at %s (with SSE at /sse and /mcp/sse)...", addr)
		if err := http.ListenAndServe(addr, mux); err != nil {
			log.Fatalf("streamable-http server error: %v", err)
		}

	default:
		log.Fatalf("Unknown transport: %s (choose stdio or streamable-http)", *transport)
	}
}

func waitForAPI(ctx context.Context, pc *proxy.Client, maxSeconds int) error {
	deadline := time.Now().Add(time.Duration(maxSeconds) * time.Second)
	for time.Now().Before(deadline) {
		if err := pc.Health(ctx); err == nil {
			return nil
		}
		time.Sleep(500 * time.Millisecond)
	}
	return fmt.Errorf("timed out after %ds", maxSeconds)
}
