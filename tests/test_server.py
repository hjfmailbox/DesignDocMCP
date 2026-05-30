import json

import pytest

import designdoc_mcp.server as server_module
from designdoc_mcp.server import active_session_resource


@pytest.fixture
def server_store(tmp_path, monkeypatch):
    monkeypatch.setenv("DESIGNDOC_DATA_DIR", str(tmp_path))
    server_module._store = None
    server_module._engine = None
    yield server_module._get_store()
    server_module._store = None


class TestActiveSessionResource:
    def test_active_session_resource_no_active_session(self, server_store):
        result = active_session_resource()
        data = json.loads(result)
        assert "message" in data
        assert "No active sessions" in data["message"]

    def test_active_session_resource_returns_json(self, server_store):
        from designdoc_mcp.server import _get_engine

        engine = _get_engine()
        engine.create_session(title="Active Test", description="Test")

        result = active_session_resource()
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "session_id" in data

    def test_active_session_resource_contains_required_fields(self, server_store):
        from designdoc_mcp.server import _get_engine

        engine = _get_engine()
        engine.create_session(title="Active Test", description="Test")

        result = active_session_resource()
        data = json.loads(result)
        assert data["session_id"] is not None
        assert data["title"] == "Active Test"
        assert "phase" in data
        assert "status" in data
        assert "agent_count" in data


class TestBulkResolveMcpTool:
    def test_bulk_resolve_mcp_tool_returns_resolved(self, server_store):
        from designdoc_mcp.models import DebatePhase
        from designdoc_mcp.server import _get_engine, bulk_resolve_decision_points

        engine = _get_engine()
        session = engine.create_session(title="MCP Bulk Test", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="agent_a")

        session = engine._get(sid)
        session.current_phase = DebatePhase.CRITIC
        engine.store._save(session)

        engine.submit_decision_points(
            sid,
            "agent_a",
            [
                {
                    "topic": "Database",
                    "description": "Choose DB",
                    "options": [
                        {"label": "PostgreSQL", "reasoning": "Reliable"},
                    ],
                    "constraints": [],
                }
            ],
        )

        result = bulk_resolve_decision_points(sid, strategy="majority", preview=False)
        assert "resolved" in result
        assert "skipped" in result
        assert len(result["resolved"]) == 1
        assert result["resolved"][0]["topic"] == "Database"
        assert result["preview"] is False

    def test_bulk_resolve_mcp_tool_preview_mode(self, server_store):
        from designdoc_mcp.models import DebatePhase
        from designdoc_mcp.server import _get_engine, bulk_resolve_decision_points

        engine = _get_engine()
        session = engine.create_session(title="MCP Preview Test", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="agent_a")

        session = engine._get(sid)
        session.current_phase = DebatePhase.CRITIC
        engine.store._save(session)

        engine.submit_decision_points(
            sid,
            "agent_a",
            [
                {
                    "topic": "Cache",
                    "description": "Choose cache",
                    "options": [
                        {"label": "Redis", "reasoning": "Fast"},
                    ],
                    "constraints": [],
                }
            ],
        )

        result = bulk_resolve_decision_points(sid, strategy="majority", preview=True)
        assert result["preview"] is True
        assert len(result["resolved"]) == 1
        assert result["resolved"][0]["chosen_label"] == "Redis"

        # Verify session was not modified
        session = engine._get(sid)
        assert session.decision_points[0].human_choice == ""
