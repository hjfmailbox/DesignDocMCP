#!/usr/bin/env python3
"""
MCP Compatibility Lab — standalone test servers for agent compatibility validation.

Does NOT depend on DesignDocMCP runtime.
Does NOT affect the main MCP server.

Usage:
    uv run python scripts/start_mcp_lab.py --all
    uv run python scripts/start_mcp_lab.py --http
    uv run python scripts/start_mcp_lab.py --sse
    uv run python scripts/start_mcp_lab.py --dual
    uv run python scripts/start_mcp_lab.py --http --sse
"""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path

import uvicorn
from fastmcp import FastMCP
from starlette.applications import Starlette

# ---------------------------------------------------------------------------
# Tools (shared across all lab servers — deterministic, no side effects)
# ---------------------------------------------------------------------------

def _register_tools(mcp: FastMCP) -> None:
    """Register the fixed lab toolset on a FastMCP instance."""

    @mcp.tool()
    def ping() -> str:
        """Return 'pong'."""
        return "pong"

    @mcp.tool()
    def echo(text: str) -> str:
        """Echo the input text back unchanged."""
        return text

    @mcp.tool()
    def multiply(a: int, b: int) -> int:
        """Return a * b."""
        return a * b


# ---------------------------------------------------------------------------
# Server factories
# ---------------------------------------------------------------------------

def build_http_app() -> Starlette:
    """StreamableHTTP only — /mcp"""
    mcp = FastMCP("mcp-lab-http")
    _register_tools(mcp)
    return mcp.http_app(transport="streamable-http")


def build_sse_app() -> Starlette:
    """SSE only — /sse (+ /messages)"""
    mcp = FastMCP("mcp-lab-sse")
    _register_tools(mcp)
    return mcp.http_app(transport="sse")


def build_dual_app() -> Starlette:
    """Dual mode — /mcp (StreamableHTTP) + /sse (+ /messages)"""
    from contextlib import AsyncExitStack, asynccontextmanager

    mcp = FastMCP("mcp-lab-dual")
    _register_tools(mcp)

    sse_app = mcp.http_app(transport="sse")
    http_app = mcp.http_app(transport="streamable-http")

    routes = list(sse_app.routes) + list(http_app.routes)

    @asynccontextmanager
    async def combined_lifespan(app):
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(sse_app.lifespan(app))
            await stack.enter_async_context(http_app.lifespan(app))
            yield

    return Starlette(routes=routes, lifespan=combined_lifespan)


# ---------------------------------------------------------------------------
# Internal server runner (used by subprocess)
# ---------------------------------------------------------------------------

def _run_single(kind: str, port: int) -> None:
    """Run one server kind in its own process."""
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    builders = {
        "http": build_http_app,
        "sse": build_sse_app,
        "dual": build_dual_app,
    }
    app = builders[kind]()
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="MCP Compatibility Lab — start test servers",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Start StreamableHTTP server on port 9101",
    )
    parser.add_argument(
        "--sse",
        action="store_true",
        help="Start SSE server on port 9102",
    )
    parser.add_argument(
        "--dual",
        action="store_true",
        help="Start dual-mode server on port 9103",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Start all three servers (9101, 9102, 9103)",
    )
    parser.add_argument(
        "--_run",
        choices=["http", "sse", "dual"],
        dest="internal_run",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    # Internal subprocess entry point ------------------------------------------------
    if args.internal_run:
        ports = {"http": 9101, "sse": 9102, "dual": 9103}
        _run_single(args.internal_run, ports[args.internal_run])
        return

    # Normal orchestrator entry point ------------------------------------------------
    if not any([args.http, args.sse, args.dual, args.all]):
        parser.print_help()
        sys.exit(1)

    servers: list[tuple[str, int, str]] = []

    if args.http or args.all:
        servers.append(("HTTP", 9101, "/mcp"))
    if args.sse or args.all:
        servers.append(("SSE", 9102, "/sse"))
    if args.dual or args.all:
        servers.append(("DUAL", 9103, "/mcp + /sse"))

    procs: list[subprocess.Popen[str]] = []
    script_path = str(Path(__file__).resolve())

    print("=" * 60)
    print("MCP Compatibility Lab")
    print("=" * 60)

    for kind, port, endpoint in servers:
        cmd = [sys.executable, script_path, f"--_run={kind.lower()}"]
        # On Windows, creationflags helps child processes receive Ctrl+C
        kwargs: dict = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        p = subprocess.Popen(cmd, **kwargs)
        procs.append(p)
        print(f"[{kind}] running at http://localhost:{port}{endpoint}")

    print("-" * 60)
    print("Press Ctrl+C to stop all servers")
    print("=" * 60)

    try:
        while True:
            time.sleep(1)
            # Poll children; if any died unexpectedly, report it
            for kind, port, _ in servers:
                idx = [s[0] for s in servers].index(kind)
                if procs[idx].poll() is not None:
                    print(f"WARNING: [{kind}] server on port {port} exited early (code {procs[idx].returncode})")
    except KeyboardInterrupt:
        print("\nStopping MCP lab servers ...")
        for p in procs:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
        print("All servers stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
