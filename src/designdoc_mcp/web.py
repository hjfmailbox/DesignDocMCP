from __future__ import annotations

import asyncio
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .engine import CollaborationEngine
from .events import event_bus
from .models import DebatePhase, SessionStatus, VoteType
from .store import SessionStore
from .constants import DEFAULT_MAX_ROUNDS, DEFAULT_MIN_ROUNDS, SSE_KEEPALIVE_SECONDS
from .document import generate_design_document

_STATIC_DIR = Path(__file__).parent / "static"

_store: SessionStore | None = None
_engine: CollaborationEngine | None = None

_API_TOKEN: str | None = None


def _get_api_token() -> str | None:
    global _API_TOKEN
    if _API_TOKEN is None:
        _API_TOKEN = os.environ.get("DESIGNDOC_API_TOKEN", "")
    return _API_TOKEN if _API_TOKEN else None


async def _verify_token(request: Request) -> None:
    token = _get_api_token()
    if not token:
        return
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        candidate = auth[7:]
    else:
        candidate = request.query_params.get("token", "")
    if not secrets.compare_digest(candidate, token):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _get_store() -> SessionStore:
    global _store
    if _store is None:
        from .server import _get_store as _server_get_store
        _store = _server_get_store()
    return _store


def _get_engine() -> CollaborationEngine:
    global _engine
    if _engine is None:
        from .server import _get_engine as _server_get_engine
        _engine = _server_get_engine()
    return _engine


web_app = FastAPI(title="DesignDoc MCP - Web UI")


@web_app.get("/", response_class=HTMLResponse)
async def index():
    html = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@web_app.get("/api/sessions")
async def list_sessions(limit: int = 0, offset: int = 0, status: str | None = None):
    store = _get_store()
    sessions = store.list_sessions(status=status, limit=limit, offset=offset)
    total = len(store.list_sessions(status=status))
    result = []
    for s in sessions:
        agents_info = []
        for a in s.agents:
            agents_info.append({
                "agent_id": a.agent_id,
                "name": a.name,
                "model": a.model,
                "provider": a.provider,
                "perspective": a.current_perspective,
                "is_active": a.is_active,
                "last_active_at": a.last_active_at,
            })
        result.append({
            "session_id": s.session_id,
            "title": s.title,
            "status": s.status.value,
            "phase": s.current_phase.value,
            "round": s.current_round,
            "agents": agents_info,
            "clarity_score": s.requirement.clarity_score if s.requirement else 0,
            "skip_clarification": s.requirement.skip_clarification if s.requirement else False,
            "needs_human": _check_needs_human(s),
        })
    return {"total": total, "limit": limit, "offset": offset, "sessions": result}


@web_app.get("/api/sessions/stalled")
async def list_stalled_sessions_api():
    engine = _get_engine()
    return {"stalled_sessions": engine.list_stalled_sessions()}


@web_app.get("/api/sessions/{session_id}")
async def get_session_detail(session_id: str):
    store = _get_store()
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _serialize_session(session)


@web_app.get("/api/sessions/{session_id}/diagnostics")
async def get_session_diagnostics_api(session_id: str):
    engine = _get_engine()
    try:
        return engine.get_session_diagnostics(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@web_app.get("/api/sessions/{session_id}/events")
async def session_event_stream(session_id: str):
    async def event_generator():
        queue = event_bus.subscribe(session_id)
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=SSE_KEEPALIVE_SECONDS)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        finally:
            event_bus.unsubscribe(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@web_app.get("/api/sessions/{session_id}/document")
async def get_session_document(session_id: str):
    store = _get_store()
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"document": generate_design_document(session)}


@web_app.post("/api/sessions/{session_id}/review-assumptions")
async def review_assumptions_api(session_id: str, request: Request, _auth=Depends(_verify_token)):
    body = await request.json()
    choices = body.get("choices", [])
    engine = _get_engine()
    engine.review_assumptions(session_id, choices)
    return {"status": "ok"}


@web_app.post("/api/sessions/{session_id}/approve-refined-requirement")
async def approve_refined_requirement_api(session_id: str, request: Request, _auth=Depends(_verify_token)):
    body = await request.json()
    refine_id = body.get("refine_id", "")
    engine = _get_engine()
    req = engine.approve_refined_requirement(session_id, refine_id)
    return {"status": "ok", "requirement_id": req.requirement_id}


@web_app.post("/api/sessions/{session_id}/resolve-question")
async def resolve_question_api(session_id: str, request: Request, _auth=Depends(_verify_token)):
    body = await request.json()
    question_id = body.get("question_id", "")
    choice = body.get("choice", "")
    engine = _get_engine()
    engine.resolve_question(session_id, question_id, choice)
    return {"status": "ok"}


@web_app.post("/api/sessions/{session_id}/human-decision")
async def human_decision_api(session_id: str, request: Request, _auth=Depends(_verify_token)):
    body = await request.json()
    action = body.get("action", "")
    reason = body.get("reason", "")
    decision = body.get("decision", "")
    rationale = body.get("rationale", "")
    engine = _get_engine()
    try:
        if action == "approve":
            engine.human_approve(session_id, "human", comment=reason)
        elif action == "reject":
            engine.human_reject(session_id, "human", reason=reason)
        elif action == "override":
            engine.human_override(session_id, "human", decision=decision or action, rationale=rationale or reason)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@web_app.post("/api/sessions/{session_id}/force-skip-clarification")
async def force_skip_clarification_api(session_id: str, _auth=Depends(_verify_token)):
    engine = _get_engine()
    try:
        result = engine.force_skip_clarification(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@web_app.post("/api/sessions/{session_id}/check-stalled")
async def check_stalled_api(session_id: str, _auth=Depends(_verify_token)):
    engine = _get_engine()
    return engine.check_stalled(session_id)


@web_app.post("/api/sessions/{session_id}/heartbeat/{agent_id}")
async def heartbeat_api(session_id: str, agent_id: str, _auth=Depends(_verify_token)):
    engine = _get_engine()
    return engine.heartbeat(session_id, agent_id)


@web_app.post("/api/sessions/create")
async def create_session_api(request: Request, _auth=Depends(_verify_token)):
    body = await request.json()
    title = body.get("title", "")
    description = body.get("description", "")
    min_rounds = body.get("min_rounds", DEFAULT_MIN_ROUNDS)
    max_rounds = body.get("max_rounds", DEFAULT_MAX_ROUNDS)
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    engine = _get_engine()
    session = engine.create_session(title, description, min_rounds=min_rounds, max_rounds=max_rounds)
    return {"session_id": session.session_id, "title": session.title}


@web_app.post("/api/sessions/{session_id}/submit-requirement")
async def submit_requirement_api(session_id: str, request: Request, _auth=Depends(_verify_token)):
    body = await request.json()
    engine = _get_engine()
    result = engine.submit_requirement(
        session_id,
        problem_statement=body.get("problem_statement", ""),
        constraints=body.get("constraints", []),
        acceptance_criteria=body.get("acceptance_criteria", []),
        open_questions=body.get("open_questions", []),
        tech_preferences=body.get("tech_preferences", []),
        forbidden_items=body.get("forbidden_items", []),
    )
    return result


@web_app.post("/api/register-agent")
async def register_agent_auto_api(request: Request, _auth=Depends(_verify_token)):
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    name = body.get("name", "")
    model = body.get("model", "")
    provider = body.get("provider", "")
    session_id = body.get("session_id", "")
    agent_identity = body.get("agent_identity", "")
    client_type = body.get("client_type", "")
    engine = _get_engine()
    try:
        result = engine.register_agent(session_id=session_id, name=name, model=model, provider=provider, agent_identity=agent_identity, client_type=client_type)
        if isinstance(result, dict):
            return result
        resolved_sid = session_id
        if not resolved_sid:
            active = [s for s in engine.store.list_sessions() if s.status not in (SessionStatus.ARCHIVED, SessionStatus.COMPLETED)]
            if len(active) == 1:
                resolved_sid = active[0].session_id
        return {
            "action": "rejoined" if getattr(result, "_rejoined", False) else "registered",
            "agent_id": result.agent_id,
            "session_id": resolved_sid,
            "name": result.name,
            "model": result.model,
            "rejoined": getattr(result, "_rejoined", False),
            "runtime_mode": result.runtime_mode,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@web_app.post("/api/sessions/{session_id}/register-agent")
async def register_agent_api(session_id: str, request: Request, _auth=Depends(_verify_token)):
    body = await request.json()
    name = body.get("name", "")
    model = body.get("model", "")
    provider = body.get("provider", "")
    agent_identity = body.get("agent_identity", "")
    client_type = body.get("client_type", "")
    engine = _get_engine()
    try:
        result = engine.register_agent(session_id=session_id, name=name, model=model, provider=provider, agent_identity=agent_identity, client_type=client_type)
        if isinstance(result, dict):
            return result
        return {
            "action": "rejoined" if getattr(result, "_rejoined", False) else "registered",
            "agent_id": result.agent_id,
            "name": result.name,
            "model": result.model,
            "rejoined": getattr(result, "_rejoined", False),
            "runtime_mode": result.runtime_mode,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@web_app.post("/api/sessions/{session_id}/start-clarification")
async def start_clarification_api(session_id: str, _auth=Depends(_verify_token)):
    engine = _get_engine()
    try:
        result = engine.start_clarification(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@web_app.post("/api/sessions/{session_id}/generate-document")
async def generate_document_api(session_id: str, _auth=Depends(_verify_token)):
    store = _get_store()
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status not in (SessionStatus.COMPLETED, SessionStatus.HUMAN_REVIEW):
        raise HTTPException(status_code=400, detail=f"Session is in '{session.status.value}' status. Please complete the debate before generating the design document.")
    doc = generate_design_document(session)
    return {"document": doc}


@web_app.post("/api/sessions/{session_id}/archive")
async def archive_session_api(session_id: str, _auth=Depends(_verify_token)):
    engine = _get_engine()
    try:
        engine.archive_session(session_id)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@web_app.post("/api/sessions/{session_id}/pause")
async def pause_session_api(session_id: str, _auth=Depends(_verify_token)):
    engine = _get_engine()
    try:
        return engine.pause_session(session_id=session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@web_app.post("/api/sessions/{session_id}/resume")
async def resume_session_api(session_id: str, _auth=Depends(_verify_token)):
    engine = _get_engine()
    try:
        return engine.resume_session(session_id=session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@web_app.post("/api/sessions/{session_id}/resolve-decision-point")
async def resolve_decision_point_api(session_id: str, request: Request, _auth=Depends(_verify_token)):
    body = await request.json()
    decision_id = body.get("decision_id", "")
    choice = body.get("choice", "")
    custom = body.get("custom", "")
    engine = _get_engine()
    try:
        result = engine.resolve_decision_point(session_id=session_id, decision_id=decision_id, choice=choice, custom=custom)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@web_app.get("/api/sessions/{session_id}/decision-points")
async def get_decision_points_api(session_id: str):
    store = _get_store()
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return [dp.model_dump() for dp in session.decision_points]


@web_app.post("/api/sessions/{session_id}/bulk-resolve-decisions")
async def bulk_resolve_decisions_api(session_id: str, request: Request, _auth=Depends(_verify_token)):
    body = await request.json()
    strategy = body.get("strategy", "majority")
    preview = body.get("preview", False)
    store = _get_store()
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    engine = _get_engine()
    try:
        result = engine.bulk_resolve_decision_points(
            session_id=session_id,
            strategy=strategy,
            preview=preview,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@web_app.delete("/api/sessions/{session_id}")
async def delete_session_api(session_id: str, _auth=Depends(_verify_token)):
    store = _get_store()
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    store.delete_session(session_id)
    return {"status": "ok"}


@web_app.post("/api/sessions/{session_id}/upload-requirement")
async def upload_requirement_api(session_id: str, request: Request, _auth=Depends(_verify_token)):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        if file is None:
            raise HTTPException(status_code=400, detail="No file provided")
        text = (await file.read()).decode("utf-8", errors="replace")
    else:
        body = await request.json()
        text = body.get("content", "")

    engine = _get_engine()
    result = engine.submit_requirement(session_id, problem_statement=text)
    return result


@web_app.post("/api/sessions/{session_id}/add-requirement-delta")
async def add_requirement_delta_api(session_id: str, request: Request, _auth=Depends(_verify_token)):
    body = await request.json()
    engine = _get_engine()
    try:
        result = engine.add_requirement_delta(
            session_id,
            delta_statement=body.get("delta_statement", ""),
            constraints=body.get("constraints", []),
            acceptance_criteria=body.get("acceptance_criteria", []),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _check_needs_human(session: Any) -> bool:
    if session.status == SessionStatus.HUMAN_REVIEW:
        return True
    if session.current_phase == DebatePhase.CLARIFY_REVIEW and session.merged_assumptions:
        if any(not a.human_choice for g in session.merged_assumptions for a in g.assumptions):
            return True
    if session.current_phase == DebatePhase.CLARIFY_REWRITE and session.refined_requirements:
        return True
    if any(not q.resolved for q in session.pending_questions):
        return True
    return False


def _time_ago(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = (now - dt).total_seconds()
        if diff < 60:
            return "just now"
        if diff < 3600:
            return f"{int(diff/60)}m ago"
        if diff < 86400:
            return f"{int(diff/3600)}h ago"
        return f"{int(diff/86400)}d ago"
    except Exception:
        return ""


def _serialize_session(session: Any) -> dict[str, Any]:
    agents = []
    for a in session.agents:
        agents.append({
            "agent_id": a.agent_id,
            "name": a.name,
            "model": a.model,
            "provider": a.provider,
            "agent_identity": a.agent_identity,
            "client_type": a.client_type,
            "runtime_mode": a.runtime_mode,
            "perspective": a.current_perspective,
            "is_active": a.is_active,
            "last_active_at": a.last_active_at,
            "last_active_ago": _time_ago(a.last_active_at),
        })

    pending_questions = []
    for q in session.pending_questions:
        if not q.resolved:
            pending_questions.append({
                "question_id": q.question_id,
                "asked_by": q.asked_by,
                "question": q.question,
                "options": [{"label": o.label, "description": o.description} for o in q.options],
            })

    events = []
    for e in session.events[-100:]:
        events.append({
            "event_id": e.event_id,
            "type": e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
            "source": e.source_agent,
            "target": e.target_agent,
            "content": e.content,
            "phase": e.phase.value if hasattr(e.phase, "value") else str(e.phase),
            "round": e.round_number,
            "created_at": e.created_at,
        })

    proposals = []
    for p in session.proposals:
        proposals.append({
            "proposal_id": p.proposal_id,
            "agent_id": p.agent_id,
            "architecture": p.architecture,
            "tech_stack": p.tech_stack,
            "tradeoffs": p.tradeoffs,
            "risks": p.risks,
            "perspective": p.perspective,
            "round": p.round_number,
        })

    challenges = []
    for c in session.challenges:
        challenges.append({
            "challenge_id": c.challenge_id,
            "agent_id": c.agent_id,
            "target_agent_id": c.target_agent_id,
            "target_proposal_id": c.target_proposal_id,
            "risks": c.risks,
            "missing_considerations": c.missing_considerations,
            "category": c.category.value if hasattr(c.category, "value") else str(c.category),
            "priority": c.priority.value if hasattr(c.priority, "value") else str(c.priority),
            "round": c.round_number,
        })

    revisions = []
    for r in session.revisions:
        revisions.append({
            "revision_id": r.revision_id,
            "agent_id": r.agent_id,
            "accepted_feedback": r.accepted_feedback,
            "rejected_feedback": r.rejected_feedback,
            "changed_design": r.changed_design,
            "round": r.round_number,
        })

    optimizations = []
    for o in session.optimizations:
        optimizations.append({
            "optimization_id": o.optimization_id,
            "agent_id": o.agent_id,
            "description": o.description,
            "impact": o.impact,
            "tradeoff": o.tradeoff,
            "round": o.round_number,
        })

    devils_advocates = []
    for d in session.devils_advocates:
        devils_advocates.append({
            "da_id": d.da_id,
            "agent_id": d.agent_id,
            "failure_modes": d.failure_modes,
            "risk_score": d.risk_score,
            "mitigation": d.mitigation,
            "round": d.round_number,
        })

    votes = []
    for v in session.consensus_votes:
        votes.append({
            "agent_id": v.agent_id,
            "vote_type": v.vote_type.value if hasattr(v.vote_type, "value") else str(v.vote_type),
            "comment": v.comment,
            "round": v.round_number,
        })

    needs_human = False
    human_actions: list[str] = []
    if session.status == SessionStatus.HUMAN_REVIEW:
        needs_human = True
        human_actions.append("review_debate")
    if session.current_phase == DebatePhase.CLARIFY_REVIEW and session.merged_assumptions:
        unresolved = any(not a.human_choice for g in session.merged_assumptions for a in g.assumptions)
        if unresolved:
            needs_human = True
            human_actions.append("review_assumptions")
    if session.current_phase == DebatePhase.CLARIFY_REWRITE and session.refined_requirements:
        needs_human = True
        human_actions.append("approve_refined_requirement")
    if pending_questions:
        needs_human = True
        human_actions.append("resolve_questions")

    event_timeline = []
    prev_phase = DebatePhase.CREATED.value
    for e in session.events:
        curr_phase = e.phase.value
        if curr_phase != prev_phase:
            event_timeline.append({
                "from_phase": prev_phase,
                "to_phase": curr_phase,
                "timestamp": e.created_at,
            })
            prev_phase = curr_phase

    phase_progress = []
    phase_order = [
        ("clarify_identify", "Identify"),
        ("clarify_refine", "Refine"),
        ("clarify_review", "Review"),
        ("clarify_rewrite", "Rewrite"),
        ("proposal", "Proposal"),
        ("critic", "Critic"),
        ("revision", "Revision"),
        ("optimization", "Optimize"),
        ("devils_advocate", "Devil's Adv."),
        ("consensus", "Consensus"),
    ]
    current_phase = session.current_phase.value
    found_current = False
    for key, label in phase_order:
        status_val = "done"
        if not found_current and key == current_phase:
            status_val = "active"
            found_current = True
        elif not found_current:
            status_val = "done"
        else:
            status_val = "pending"
        phase_progress.append({"key": key, "label": label, "status": status_val})

    return {
        "session_id": session.session_id,
        "title": session.title,
        "description": session.description,
        "status": session.status.value,
        "phase": session.current_phase.value,
        "round": session.current_round,
        "min_rounds": session.min_rounds,
        "max_rounds": session.max_rounds,
        "agents": agents,
        "requirement": {
            "problem_statement": session.requirement.problem_statement if session.requirement else "",
            "constraints": session.requirement.constraints if session.requirement else [],
            "acceptance_criteria": session.requirement.acceptance_criteria if session.requirement else [],
            "clarity_score": session.requirement.clarity_score if session.requirement else 0,
            "skip_clarification": session.requirement.skip_clarification if session.requirement else False,
            "is_refined": session.requirement.is_refined if session.requirement else False,
        } if session.requirement else None,
        "assumptions": [
            {
                "assumption_id": a.assumption_id,
                "agent_id": a.agent_id,
                "dimension": a.dimension,
                "assumption": a.assumption,
                "confidence": a.confidence,
                "alternatives": [{"label": alt.label, "description": alt.description} for alt in a.alternatives],
                "human_choice": a.human_choice,
                "clarify_round": a.clarify_round,
            }
            for a in session.assumptions
        ] if session.assumptions else [],
        "merged_assumptions": [
            {
                "dimension": g.dimension,
                "divergent": g.divergent,
                "assumptions": [
                    {
                        "assumption_id": a.assumption_id,
                        "agent_id": a.agent_id,
                        "assumption": a.assumption,
                        "confidence": a.confidence,
                        "alternatives": [{"label": alt.label, "description": alt.description} for alt in a.alternatives],
                        "human_choice": a.human_choice,
                    }
                    for a in g.assumptions
                ],
            }
            for g in session.merged_assumptions
        ] if session.merged_assumptions else [],
        "refined_requirements": [
            {
                "refine_id": r.refine_id,
                "agent_id": r.agent_id,
                "refined_statement": r.refined_statement[:200] + "..." if len(r.refined_statement) > 200 else r.refined_statement,
            }
            for r in session.refined_requirements
        ] if session.refined_requirements else [],
        "proposals": proposals,
        "challenges": challenges,
        "revisions": revisions,
        "optimizations": optimizations,
        "devils_advocates": devils_advocates,
        "votes": votes,
        "pending_questions": pending_questions,
        "decision_points": [
            {
                "decision_id": dp.decision_id,
                "topic": dp.topic,
                "description": dp.description,
                "options": [
                    {
                        "option_id": o.option_id,
                        "label": o.label,
                        "proposed_by": o.proposed_by,
                        "reasoning": o.reasoning,
                        "pros": o.pros,
                        "cons": o.cons,
                    }
                    for o in dp.options
                ],
                "constraints": dp.constraints,
                "human_choice": dp.human_choice,
                "human_custom": dp.human_custom,
            }
            for dp in session.decision_points
        ] if session.decision_points else [],
        "events": events,
        "event_timeline": event_timeline,
        "phase_progress": phase_progress,
        "needs_human": needs_human,
        "human_actions": human_actions,
        "human_review_reason": session.metadata.get("human_review_reason", ""),
    }


if _STATIC_DIR.exists():
    web_app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
