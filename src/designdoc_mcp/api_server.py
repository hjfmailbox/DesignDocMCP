"""HTTP API server for Python Engine — called by Go MCP gateway."""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .engine import CollaborationEngine
from .store import SessionStore

_store: SessionStore | None = None
_engine: CollaborationEngine | None = None


def _serialize(obj: Any) -> Any:
    """Serialize Pydantic models to JSON-safe dicts (enums → strings)."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


def _get_store() -> SessionStore:
    global _store
    if _store is None:
        storage_backend = os.environ.get("DESIGNDOC_STORAGE", "json").lower()
        data_dir = os.environ.get("DESIGNDOC_DATA_DIR")
        if storage_backend == "sqlite":
            from .sqlite_store import SQLiteBackend
            _store = SQLiteBackend(data_dir)  # type: ignore[assignment]
        else:
            _store = SessionStore(data_dir)
    return _store


def _get_engine() -> CollaborationEngine:
    global _engine
    if _engine is None:
        _engine = CollaborationEngine(_get_store())
    return _engine


api_app = FastAPI(title="DesignDoc Engine API", version="0.3.0")


@api_app.exception_handler(ValueError)
async def _value_error_handler(_req: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------
@api_app.post("/api/v1/create_session")
async def create_session(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    session = engine.create_session(
        title=body.get("title", ""),
        description=body.get("description", ""),
        min_rounds=body.get("min_rounds", 4),
        max_rounds=body.get("max_rounds", 8),
    )
    return _serialize(session)


@api_app.post("/api/v1/list_sessions")
async def list_sessions(body: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    store = _get_store()
    status = (body or {}).get("status")
    sessions = store.list_sessions(status)
    return [
        {
            "session_id": s.session_id,
            "title": s.title,
            "status": s.status.value,
            "current_phase": s.current_phase.value,
            "current_round": s.current_round,
            "agents_count": len(s.agents),
        }
        for s in sessions
    ]


@api_app.post("/api/v1/get_session")
async def get_session(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_session(body["session_id"])
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result.model_dump(mode="json") if hasattr(result, "model_dump") else result


@api_app.post("/api/v1/delete_session")
async def delete_session(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.delete_session(body["session_id"])


@api_app.post("/api/v1/submit_requirement")
async def submit_requirement(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    req = engine.submit_requirement(
        session_id=body["session_id"],
        requirement=body["requirement"],
    )
    return _serialize(req)


# ---------------------------------------------------------------------------
# Agent management
# ---------------------------------------------------------------------------
@api_app.post("/api/v1/register_agent")
async def register_agent(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.register_agent(
        session_id=body.get("session_id", ""),
        name=body.get("name", ""),
        model=body.get("model"),
        provider=body.get("provider"),
        agent_identity=body.get("agent_identity"),
        client_type=body.get("client_type"),
        client_info_hint=body.get("client_info_hint", ""),
        force_mode=body.get("force_mode", ""),
    )
    if isinstance(result, dict):
        return result
    return result.model_dump(mode="json")


@api_app.post("/api/v1/deregister_agent")
async def deregister_agent(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.deregister_agent(body["session_id"], body["agent_id"])


@api_app.post("/api/v1/heartbeat")
async def heartbeat(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.heartbeat(body["session_id"], body["agent_id"])


# ---------------------------------------------------------------------------
# Task lifecycle
# ---------------------------------------------------------------------------
@api_app.post("/api/v1/wait_for_task")
async def wait_for_task(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.wait_for_task_engine(
        session_id=body["session_id"],
        agent_id=body["agent_id"],
        timeout=body.get("timeout", 25),
    )


@api_app.post("/api/v1/submit_result")
async def submit_result(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.submit_result_engine(
        session_id=body["session_id"],
        agent_id=body["agent_id"],
        task_id=body["task_id"],
        result=body["result"],
    )


# ---------------------------------------------------------------------------
# Phase context
# ---------------------------------------------------------------------------
@api_app.post("/api/v1/get_phase_context")
async def get_phase_context(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_phase_context(body["session_id"], body["agent_id"])


@api_app.post("/api/v1/start_clarification")
async def start_clarification(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.start_clarification(body["session_id"])


@api_app.post("/api/v1/start_debate")
async def start_debate(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.start_debate(body["session_id"])


# ---------------------------------------------------------------------------
# Submission endpoints
# ---------------------------------------------------------------------------
@api_app.post("/api/v1/submit_assumptions")
async def submit_assumptions(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.submit_assumptions(
        session_id=body["session_id"],
        agent_id=body["agent_id"],
        assumptions=body["assumptions"],
    )


@api_app.post("/api/v1/submit_refined_requirement")
async def submit_refined_requirement(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.submit_refined_requirement(
        session_id=body["session_id"],
        agent_id=body["agent_id"],
        refined=body["refined"],
    )


@api_app.post("/api/v1/submit_proposal")
async def submit_proposal(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.submit_proposal(
        session_id=body["session_id"],
        agent_id=body["agent_id"],
        proposal=body["proposal"],
    )


@api_app.post("/api/v1/submit_challenge")
async def submit_challenge(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.submit_challenge(
        session_id=body["session_id"],
        agent_id=body["agent_id"],
        challenge=body["challenge"],
    )


@api_app.post("/api/v1/submit_revision")
async def submit_revision(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.submit_revision(
        session_id=body["session_id"],
        agent_id=body["agent_id"],
        revision=body["revision"],
    )


@api_app.post("/api/v1/submit_optimization")
async def submit_optimization(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.submit_optimization(
        session_id=body["session_id"],
        agent_id=body["agent_id"],
        optimization=body["optimization"],
    )


@api_app.post("/api/v1/submit_devils_advocate")
async def submit_devils_advocate(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.submit_devils_advocate(
        session_id=body["session_id"],
        agent_id=body["agent_id"],
        devils_advocate=body["devils_advocate"],
    )


@api_app.post("/api/v1/cast_consensus_vote")
async def cast_consensus_vote(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.cast_consensus_vote(
        session_id=body["session_id"],
        agent_id=body["agent_id"],
        vote=body["vote"],
    )


# ---------------------------------------------------------------------------
# Human review
# ---------------------------------------------------------------------------
@api_app.post("/api/v1/request_human_review")
async def request_human_review(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.request_human_review(body["session_id"])


@api_app.post("/api/v1/human_approve")
async def human_approve(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.human_approve(
        body["session_id"], body["approver"], body.get("comment", "")
    )


@api_app.post("/api/v1/human_reject")
async def human_reject(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.human_reject(body["session_id"], body["approver"], body["reason"])


@api_app.post("/api/v1/human_override")
async def human_override(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.human_override(
        body["session_id"], body["approver"], body["decision"], body["rationale"]
    )


# ---------------------------------------------------------------------------
# Utility / query
# ---------------------------------------------------------------------------
@api_app.post("/api/v1/get_session_flow")
async def get_session_flow(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_session_flow(body["session_id"])


@api_app.post("/api/v1/check_stalled")
async def check_stalled(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.check_stalled(body["session_id"])


@api_app.post("/api/v1/get_session_diagnostics")
async def get_session_diagnostics(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_session_diagnostics(body["session_id"])


@api_app.post("/api/v1/generate_design_document")
async def generate_design_document(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return {"document": engine.generate_design_document(body["session_id"])}


@api_app.post("/api/v1/add_requirement_delta")
async def add_requirement_delta(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.add_requirement_delta(
        body["session_id"], body["agent_id"], body["delta"]
    )


@api_app.post("/api/v1/force_skip_clarification")
async def force_skip_clarification(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.force_skip_clarification(body["session_id"])


@api_app.post("/api/v1/pause_session")
async def pause_session(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.pause_session(body["session_id"])


@api_app.post("/api/v1/resume_session")
async def resume_session(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.resume_session(body["session_id"])


@api_app.post("/api/v1/archive_session")
async def archive_session(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.archive_session(body["session_id"])


def main() -> None:
    import uvicorn
    host = os.environ.get("DESIGNDOC_API_HOST", "127.0.0.1")
    port = int(os.environ.get("DESIGNDOC_API_PORT", "9000"))
    uvicorn.run(api_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
