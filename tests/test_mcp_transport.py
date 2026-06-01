"""Smoke tests for MCP transport compatibility.

Verifies that the DesignDoc MCP server app exposes both:
- StreamableHTTP on /mcp
- SSE on /sse

Full protocol behaviour (initialize, tools/list, endpoint events) is validated
manually via scripts/start_mcp_lab.py and curl.  These tests only confirm the
routes are wired correctly in the combined Starlette app.
"""
from __future__ import annotations

import pytest
from starlette.applications import Starlette

from designdoc_mcp.server import mcp


def _build_combined_app() -> Starlette:
    """Build the same combined Starlette app that main() uses."""
    from contextlib import AsyncExitStack, asynccontextmanager

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


@pytest.fixture
def combined_app():
    """Provide the combined MCP Starlette app."""
    return _build_combined_app()


class TestMcpTransport:
    def test_streamable_http_route_present(self, combined_app):
        """The combined app must expose /mcp (StreamableHTTP)."""
        routes = [r.path for r in combined_app.routes if hasattr(r, "path")]
        assert "/mcp" in routes

    def test_sse_route_present(self, combined_app):
        """The combined app must expose /sse (SSE)."""
        routes = [r.path for r in combined_app.routes if hasattr(r, "path")]
        assert "/sse" in routes

    def test_messages_route_present(self, combined_app):
        """The combined app must expose /messages (SSE companion)."""
        routes = [r.path for r in combined_app.routes if hasattr(r, "path")]
        assert "/messages" in routes
