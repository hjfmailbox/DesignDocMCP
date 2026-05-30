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
