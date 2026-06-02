"""HTTP API server for Python Engine — called by Go MCP gateway."""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .document import generate_design_document as _generate_design_document
from .models import SessionStatus
from .state import _get_engine, _get_store


def _serialize(obj: Any) -> Any:
    """Serialize Pydantic models to JSON-safe dicts (enums → strings)."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


def _serialize_list(obj: Any) -> Any:
    """Serialize a list of Pydantic models."""
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    return _serialize(obj)


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
    store = _get_store()
    result = store.get_session(body["session_id"])
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _serialize(result)


@api_app.post("/api/v1/delete_session")
async def delete_session(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.delete_session(body["session_id"])


@api_app.post("/api/v1/submit_requirement")
async def submit_requirement(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    req = engine.submit_requirement(
        session_id=body["session_id"],
        problem_statement=body.get("problem_statement", ""),
        constraints=body.get("constraints"),
        acceptance_criteria=body.get("acceptance_criteria"),
        open_questions=body.get("open_questions"),
        tech_preferences=body.get("tech_preferences"),
        forbidden_items=body.get("forbidden_items"),
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
    task = engine.wait_for_task_engine(
        session_id=body["session_id"],
        agent_id=body["agent_id"],
        timeout=body.get("timeout", 25),
    )
    if task is None:
        return {"status": "timeout"}
    return task


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
    store = _get_store()
    session = store.get_session(body["session_id"])
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status not in (SessionStatus.COMPLETED, SessionStatus.HUMAN_REVIEW):
        raise HTTPException(
            status_code=400,
            detail=f"Session is in '{session.status.value}' status. Complete the debate before generating the design document.",
        )
    return {"document": _generate_design_document(session)}


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


# ---------------------------------------------------------------------------
# Missing endpoints (added during hybrid refactor audit)
# ---------------------------------------------------------------------------
@api_app.post("/api/v1/advance_phase")
async def advance_phase(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.advance_phase(body["session_id"])


@api_app.post("/api/v1/advance_round")
async def advance_round(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.advance_round(body["session_id"])


@api_app.post("/api/v1/approve_refined_requirement")
async def approve_refined_requirement(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return _serialize(engine.approve_refined_requirement(body["session_id"], body["refine_id"]))


@api_app.post("/api/v1/bulk_resolve_decision_points")
async def bulk_resolve_decision_points(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.bulk_resolve_decision_points(
        body["session_id"],
        body.get("strategy", "majority"),
        body.get("preview", False),
    )


@api_app.post("/api/v1/compare_sessions")
async def compare_sessions(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.compare_sessions(body["session_id_a"], body["session_id_b"])


@api_app.post("/api/v1/get_merged_assumptions")
async def get_merged_assumptions(body: dict[str, Any]) -> list[dict[str, Any]]:
    engine = _get_engine()
    return _serialize_list(engine.get_merged_assumptions(body["session_id"]))


@api_app.post("/api/v1/get_pending_questions")
async def get_pending_questions(body: dict[str, Any]) -> list[dict[str, Any]]:
    engine = _get_engine()
    return _serialize_list(engine.get_pending_questions(body["session_id"]))


@api_app.post("/api/v1/raise_question")
async def raise_question(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return _serialize(engine.raise_question(
        body["session_id"],
        body["agent_id"],
        body["question"],
        body.get("options"),
    ))


@api_app.post("/api/v1/resolve_decision_point")
async def resolve_decision_point(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.resolve_decision_point(
        body["session_id"],
        body["decision_id"],
        body.get("choice", ""),
        body.get("custom", ""),
    )


@api_app.post("/api/v1/resolve_question")
async def resolve_question(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    engine.resolve_question(body["session_id"], body["question_id"], body["human_choice"])
    return {"ok": True}


@api_app.post("/api/v1/revert_to_event")
async def revert_to_event(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.revert_to_event(body["session_id"], body["event_id"])


@api_app.post("/api/v1/review_assumptions")
async def review_assumptions(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    engine.review_assumptions(body["session_id"], body["choices"])
    return {"ok": True}


@api_app.post("/api/v1/submit_decision_points")
async def submit_decision_points(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.submit_decision_points(
        body["session_id"], body["agent_id"], body["decision_points"]
    )


@api_app.post("/api/v1/submit_human_vote")
async def submit_human_vote(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    return engine.submit_human_vote(
        body["session_id"], body["approver"], body["vote_type"], body.get("comment", "")
    )


@api_app.post("/api/v1/supplement_assumption_options")
async def supplement_assumption_options(body: dict[str, Any]) -> dict[str, Any]:
    engine = _get_engine()
    engine.supplement_assumption_options(
        body["session_id"], body["agent_id"], body["supplements"]
    )
    return {"ok": True}


@api_app.post("/api/v1/generate_design_document_html")
async def generate_design_document_html(body: dict[str, Any]) -> dict[str, Any]:
    from .document import generate_design_document_html as _html

    store = _get_store()
    session = store.get_session(body["session_id"])
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status not in (SessionStatus.COMPLETED, SessionStatus.HUMAN_REVIEW):
        raise HTTPException(
            status_code=400,
            detail=f"Session is in '{session.status.value}' status. Complete the debate before generating the design document.",
        )
    return {"document": _html(session)}


@api_app.post("/api/v1/generate_design_document_json")
async def generate_design_document_json(body: dict[str, Any]) -> dict[str, Any]:
    from .document import generate_design_document_json as _json

    store = _get_store()
    session = store.get_session(body["session_id"])
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status not in (SessionStatus.COMPLETED, SessionStatus.HUMAN_REVIEW):
        raise HTTPException(
            status_code=400,
            detail=f"Session is in '{session.status.value}' status. Complete the debate before generating the design document.",
        )
    return {"document": _json(session)}


def main() -> None:
    import uvicorn
    host = os.environ.get("DESIGNDOC_API_HOST", "127.0.0.1")
    port = int(os.environ.get("DESIGNDOC_API_PORT", "9000"))
    uvicorn.run(api_app, host=host, port=port, log_level="info")


# Mount Web UI into the same process so port 9000 serves both API and UI.
from .web import web_app as _web_app  # noqa: E402

api_app.mount("/", _web_app)


if __name__ == "__main__":
    main()
