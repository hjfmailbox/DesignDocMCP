"""E2E API tests: HTTP → FastAPI/Web → engine → persistence → response"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from designdoc_mcp.models import SessionStatus
from designdoc_mcp.web import web_app


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """Provide an isolated TestClient with a temporary data directory."""
    monkeypatch.setenv("DESIGNDOC_DATA_DIR", str(tmp_path))
    # Reset global singletons so each test gets a fresh store/engine
    import designdoc_mcp.server as server_module
    import designdoc_mcp.web as web_module

    server_module._store = None
    server_module._engine = None
    web_module._store = None
    web_module._engine = None

    return TestClient(web_app)


class TestCreateSessionToDocumentFlow:
    def test_create_session_to_document_generation_flow(self, api_client):
        """完整链路：创建 session → 提交需求 → 完成 session → 生成文档 → 获取文档"""
        # 1. 创建 session
        resp = api_client.post("/api/sessions/create", json={"title": "E2E Test", "description": "End-to-end flow"})
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        sid = data["session_id"]

        # 2. 提交需求
        resp = api_client.post(
            f"/api/sessions/{sid}/submit-requirement",
            json={"problem_statement": "Build a user auth system", "constraints": ["Must use JWT"]},
        )
        assert resp.status_code == 200
        req_data = resp.json()
        assert req_data["problem_statement"] == "Build a user auth system"

        # 3. 通过内部 engine 直接将 session 推进到 COMPLETED（API 层验证链路）
        from designdoc_mcp.web import _get_engine

        engine = _get_engine()
        session = engine._get(sid)
        session.status = SessionStatus.COMPLETED
        session.completed_at = "2026-01-01T00:00:00"
        engine.store.update_session(session)

        # 4. 生成文档
        resp = api_client.post(f"/api/sessions/{sid}/generate-document")
        assert resp.status_code == 200
        gen_data = resp.json()
        assert "document" in gen_data
        assert "E2E Test" in gen_data["document"]

        # 5. GET /document
        resp = api_client.get(f"/api/sessions/{sid}/document")
        assert resp.status_code == 200
        doc_data = resp.json()
        assert "document" in doc_data
        assert "E2E Test" in doc_data["document"]

    def test_generate_document_guard_before_requirement(self, api_client):
        """CREATED 状态调用 generate-document 应被 guard 拒绝（Loop 1 修复覆盖）"""
        resp = api_client.post("/api/sessions/create", json={"title": "Guard Test", "description": "Test"})
        sid = resp.json()["session_id"]

        resp = api_client.post(f"/api/sessions/{sid}/generate-document")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
        assert "complete the debate" in data["error"].lower() or "CREATED" in data["error"]


class TestHumanDecisionFlow:
    def test_human_decision_approve(self, api_client):
        """HUMAN_REVIEW → approve → COMPLETED"""
        resp = api_client.post("/api/sessions/create", json={"title": "Human Decision", "description": "Test"})
        sid = resp.json()["session_id"]

        # 直接注入 HUMAN_REVIEW 状态
        from designdoc_mcp.web import _get_engine

        engine = _get_engine()
        session = engine._get(sid)
        session.status = SessionStatus.HUMAN_REVIEW
        engine.store.update_session(session)

        resp = api_client.post(
            f"/api/sessions/{sid}/human-decision",
            json={"action": "approve", "reason": "Looks good"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        session = engine._get(sid)
        assert session.status == SessionStatus.COMPLETED

    def test_human_decision_reject(self, api_client):
        """HUMAN_REVIEW → reject → PROPOSAL"""
        resp = api_client.post("/api/sessions/create", json={"title": "Human Reject", "description": "Test"})
        sid = resp.json()["session_id"]

        from designdoc_mcp.web import _get_engine

        engine = _get_engine()
        session = engine._get(sid)
        session.status = SessionStatus.HUMAN_REVIEW
        session.current_round = 2
        engine.store.update_session(session)

        resp = api_client.post(
            f"/api/sessions/{sid}/human-decision",
            json={"action": "reject", "reason": "Needs more work"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        session = engine._get(sid)
        assert session.status == SessionStatus.PROPOSAL


class TestInvalidSession:
    def test_invalid_session_returns_error_consistently(self, api_client):
        """多个 endpoint 对无效 session_id 行为一致（返回 error JSON）"""
        bad_sid = "nonexistent-session-id"

        # GET /session
        resp = api_client.get(f"/api/sessions/{bad_sid}")
        assert resp.status_code == 200
        assert "error" in resp.json()

        # POST /generate-document
        resp = api_client.post(f"/api/sessions/{bad_sid}/generate-document")
        assert resp.status_code == 200
        assert "error" in resp.json()

        # POST /human-decision
        resp = api_client.post(
            f"/api/sessions/{bad_sid}/human-decision",
            json={"action": "approve", "reason": "test"},
        )
        assert resp.status_code == 200
        assert "error" in resp.json()

        # GET /document
        resp = api_client.get(f"/api/sessions/{bad_sid}/document")
        assert resp.status_code == 200
        assert "error" in resp.json()


class TestEventStream:
    def test_event_stream_endpoint_alive(self, api_client):
        """SSE endpoint 可连接并返回正确 headers"""
        import asyncio
        from unittest.mock import MagicMock, patch

        resp = api_client.post("/api/sessions/create", json={"title": "SSE Test", "description": "Test"})
        sid = resp.json()["session_id"]

        # Mock queue to break the infinite generator quickly
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()

        with patch("designdoc_mcp.web.event_bus.subscribe", return_value=mock_queue):
            resp = api_client.get(f"/api/sessions/{sid}/events")
            assert resp.status_code == 200
            assert resp.headers.get("content-type", "").startswith("text/event-stream")


class TestSessionLifecycle:
    def test_list_sessions_after_create(self, api_client):
        """创建后 list sessions 能查到"""
        resp = api_client.post("/api/sessions/create", json={"title": "List Test", "description": "Test"})
        sid = resp.json()["session_id"]

        resp = api_client.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(s["session_id"] == sid for s in data["sessions"])

    def test_get_session_detail_structure(self, api_client):
        """GET /session 返回结构正确"""
        resp = api_client.post("/api/sessions/create", json={"title": "Detail Test", "description": "Test"})
        sid = resp.json()["session_id"]

        resp = api_client.get(f"/api/sessions/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == sid
        assert "title" in data
        assert "status" in data
        assert "phase" in data
        assert "agents" in data
