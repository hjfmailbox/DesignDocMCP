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
        assert resp.status_code == 400
        data = resp.json()
        assert "detail" in data
        assert "complete the debate" in data["detail"].lower() or "CREATED" in data["detail"]


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
    def test_invalid_session_returns_404_consistently(self, api_client):
        """多个 endpoint 对无效 session_id 行为一致（返回 HTTP 404）"""
        bad_sid = "nonexistent-session-id"

        # GET /session
        resp = api_client.get(f"/api/sessions/{bad_sid}")
        assert resp.status_code == 404
        assert "detail" in resp.json()

        # POST /generate-document
        resp = api_client.post(f"/api/sessions/{bad_sid}/generate-document")
        assert resp.status_code == 404
        assert "detail" in resp.json()

        # GET /document
        resp = api_client.get(f"/api/sessions/{bad_sid}/document")
        assert resp.status_code == 404
        assert "detail" in resp.json()

    def test_create_session_missing_title_returns_400(self, api_client):
        """创建 session 缺少 title 返回 HTTP 400"""
        resp = api_client.post("/api/sessions/create", json={"title": "", "description": "Test"})
        assert resp.status_code == 400
        assert "detail" in resp.json()

    def test_human_decision_unknown_action_returns_400(self, api_client):
        """human-decision 未知 action 返回 HTTP 400"""
        resp = api_client.post("/api/sessions/create", json={"title": "Action Test", "description": "Test"})
        sid = resp.json()["session_id"]

        from designdoc_mcp.web import _get_engine
        engine = _get_engine()
        session = engine._get(sid)
        session.status = SessionStatus.HUMAN_REVIEW
        engine.store.update_session(session)

        resp = api_client.post(
            f"/api/sessions/{sid}/human-decision",
            json={"action": "unknown", "reason": "test"},
        )
        assert resp.status_code == 400
        assert "detail" in resp.json()


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


class TestSessionPauseResumeLifecycle:
    def test_pause_resume_cycle(self, api_client):
        """session pause → resume 状态正确流转"""
        resp = api_client.post("/api/sessions/create", json={"title": "Pause Test", "description": "Test"})
        sid = resp.json()["session_id"]

        resp = api_client.post(f"/api/sessions/{sid}/pause")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paused"

        resp = api_client.get(f"/api/sessions/{sid}")
        assert resp.json()["status"] == "paused"

        resp = api_client.post(f"/api/sessions/{sid}/resume")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] != "paused"

        resp = api_client.get(f"/api/sessions/{sid}")
        assert resp.json()["status"] != "paused"

    def test_pause_already_paused_returns_400(self, api_client):
        """重复 pause 返回 400"""
        resp = api_client.post("/api/sessions/create", json={"title": "Double Pause", "description": "Test"})
        sid = resp.json()["session_id"]

        api_client.post(f"/api/sessions/{sid}/pause")
        resp = api_client.post(f"/api/sessions/{sid}/pause")
        assert resp.status_code == 400
        assert "detail" in resp.json()


class TestAgentHeartbeat:
    def test_heartbeat_updates_last_active(self, api_client):
        """heartbeat 更新 agent last_active_at"""
        resp = api_client.post("/api/sessions/create", json={"title": "Heartbeat Test", "description": "Test"})
        sid = resp.json()["session_id"]

        resp = api_client.post("/api/register-agent", json={"session_id": sid, "name": "Alpha"})
        assert resp.status_code == 200
        agent_id = resp.json()["agent_id"]

        resp = api_client.post(f"/api/sessions/{sid}/heartbeat/{agent_id}")
        assert resp.status_code == 200

        resp = api_client.get(f"/api/sessions/{sid}")
        agents = resp.json()["agents"]
        alpha = next(a for a in agents if a["agent_id"] == agent_id)
        assert alpha["last_active_ago"] == "just now"


class TestDebatePhaseTransitions:
    def test_force_skip_clarification_advances_phase(self, api_client):
        """force-skip-clarification 将 phase 从 CREATED 推进到 PROPOSAL"""
        resp = api_client.post("/api/sessions/create", json={"title": "Skip Test", "description": "Test"})
        sid = resp.json()["session_id"]

        resp = api_client.post(
            f"/api/sessions/{sid}/submit-requirement",
            json={"problem_statement": "Build a system"},
        )
        assert resp.status_code == 200

        resp = api_client.post("/api/register-agent", json={"session_id": sid, "name": "Alpha"})
        assert resp.status_code == 200

        resp = api_client.post(f"/api/sessions/{sid}/start-clarification")
        assert resp.status_code == 200

        resp = api_client.post(f"/api/sessions/{sid}/force-skip-clarification")
        assert resp.status_code == 200

        resp = api_client.get(f"/api/sessions/{sid}")
        assert resp.json()["phase"] == "proposal"

    def test_start_clarification_requires_agent(self, api_client):
        """start-clarification 在没有 agent 时返回 400"""
        resp = api_client.post("/api/sessions/create", json={"title": "Start Clarify", "description": "Test"})
        sid = resp.json()["session_id"]

        resp = api_client.post(
            f"/api/sessions/{sid}/submit-requirement",
            json={"problem_statement": "Build a system"},
        )
        assert resp.status_code == 200

        resp = api_client.post(f"/api/sessions/{sid}/start-clarification")
        assert resp.status_code == 400
        assert "detail" in resp.json()
