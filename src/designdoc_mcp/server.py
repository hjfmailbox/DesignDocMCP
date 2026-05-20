from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import logging

from fastmcp import FastMCP

from .document import generate_debate_summary, generate_design_document as _generate_design_document, generate_adr, generate_full_output, generate_human_decision_points
from .engine import CollaborationEngine
from .models import DebatePhase, SessionStatus, VoteType
from .store import SessionStore

logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="DesignDoc MCP",
    version="0.3.0",
)

_store: SessionStore | None = None
_engine: CollaborationEngine | None = None


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


@mcp.tool()
def create_session(title: str, description: str, min_rounds: int = 4, max_rounds: int = 8) -> dict[str, Any]:
    """Create a new design document collaboration session.

    The session starts in CLARIFY_IDENTIFY phase. Submit a requirement, register agents,
    then start clarification before the debate.

    Args:
        title: The title of the design document discussion
        description: Detailed description of what this session will discuss
        min_rounds: Minimum debate rounds before auto-stop (default: 4)
        max_rounds: Maximum debate rounds before forcing human review (default: 8)

    Returns:
        Session information including session_id needed for all other operations
    """
    engine = _get_engine()
    session = engine.create_session(title=title, description=description, min_rounds=min_rounds, max_rounds=max_rounds)
    return session.model_dump()


@mcp.tool()
def list_sessions(status: str | None = None) -> list[dict[str, Any]]:
    """List all collaboration sessions, optionally filtered by status.

    Args:
        status: Filter by session status. One of: created, clarify_identify, clarify_refine, clarify_review, clarify_rewrite, proposal, critic, revision, optimization, devils_advocate, consensus, human_review, completed, archived

    Returns:
        List of session summaries
    """
    store = _get_store()
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


@mcp.tool()
def get_session(session_id: str) -> dict[str, Any]:
    """Get detailed summary of a specific session including current phase, votes, and progress.

    Args:
        session_id: The session identifier

    Returns:
        Complete session summary
    """
    engine = _get_engine()
    return engine.get_session_summary(session_id)


@mcp.tool()
def get_session_flow(session_id: str) -> dict[str, Any]:
    """Get the session flow summary including key decisions, phase transitions, assumption decisions, and round summaries.

    This provides a high-level view of the entire collaboration process, useful for
    quickly understanding what happened without reading all events.

    Args:
        session_id: The session identifier

    Returns:
        Flow summary with key_decisions, assumption_decisions, and round_summaries
    """
    engine = _get_engine()
    return engine.get_session_flow(session_id)


@mcp.tool()
def submit_requirement(
    session_id: str,
    problem_statement: str,
    constraints: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    open_questions: list[str] | None = None,
    tech_preferences: list[str] | None = None,
    forbidden_items: list[str] | None = None,
) -> dict[str, Any]:
    """Submit the requirement specification for the design discussion.

    This can be a fuzzy/vague requirement. The clarification phase will help refine it.
    The requirement is also saved as a file in the data directory.

    Args:
        session_id: The session identifier
        problem_statement: Description of the problem to solve (can be vague/fuzzy)
        constraints: List of constraints that must be respected
        acceptance_criteria: List of criteria that must be met for the design to be accepted
        open_questions: Known open questions that need resolution during debate
        tech_preferences: Preferred technologies or approaches
        forbidden_items: Technologies or approaches that are explicitly forbidden

    Returns:
        The requirement specification
    """
    engine = _get_engine()
    req = engine.submit_requirement(
        session_id=session_id,
        problem_statement=problem_statement,
        constraints=constraints,
        acceptance_criteria=acceptance_criteria,
        open_questions=open_questions,
        tech_preferences=tech_preferences,
        forbidden_items=forbidden_items,
    )
    return req.model_dump()


@mcp.tool()
def register_agent(
    session_id: str = "",
    name: str = "",
    model: str = "",
    provider: str = "",
    agent_identity: str = "",
    client_type: str = "",
) -> dict[str, Any]:
    """Register yourself to a collaboration session. Call this when user says /register.

    All parameters are optional. The system will auto-detect:
    - If session_id is omitted: auto-joins the only active session, or returns a list to choose from
    - If name is omitted: defaults to "Agent"
    - agent_identity: stable identity across reconnects (e.g. "cursor_cli_local_hash")
    - client_type: your client type (cursor / claude_code / atomcode / generic)

    If agent_identity matches an existing agent, you will auto-rejoin (not create a new agent).

    Args:
        session_id: The session to join (omit to auto-discover)
        name: Your display name (e.g., "Claude Code", "Cursor Composer Agent")
        model: Your model identifier (e.g., "claude-3.5-sonnet")
        provider: Your provider (e.g., "anthropic")
        agent_identity: Stable identity for auto-rejoin across reconnects
        client_type: Client type for runtime capability detection

    Returns:
        Agent registration info with rejoined/runtime_mode/phase/pending_task
    """
    engine = _get_engine()
    logger.info("register_agent called: session_id=%r, name=%r, identity=%r, client_type=%r", session_id, name, agent_identity, client_type)
    result = engine.register_agent(
        session_id=session_id,
        name=name,
        model=model,
        provider=provider,
        agent_identity=agent_identity,
        client_type=client_type,
    )
    if isinstance(result, dict):
        logger.info("register_agent returned dict (choose/error): %s", result.get("action"))
        return result
    resolved_sid = session_id
    if not resolved_sid:
        active = [s for s in engine.store.list_sessions() if s.status.value not in ("archived", "completed")]
        if len(active) == 1:
            resolved_sid = active[0].session_id
    data = result.model_dump()
    data["session_id"] = resolved_sid
    data["rejoined"] = getattr(result, "_rejoined", False)
    data["runtime_mode"] = result.runtime_mode
    data["phase"] = result.current_perspective or ""
    logger.info("register_agent success: agent_id=%s, session_id=%s, rejoined=%s", result.agent_id, resolved_sid, data["rejoined"])

    # 自动执行 heartbeat + get_phase_context，让 agent 立即进入协作状态
    try:
        engine.heartbeat(resolved_sid, result.agent_id)
        phase_ctx = engine.get_phase_context(resolved_sid, result.agent_id)
        data["auto_heartbeat"] = "ok"
        data["phase_context"] = phase_ctx
        data["phase"] = phase_ctx.get("current_phase", data["phase"]) if isinstance(phase_ctx, dict) else data["phase"]
        # Check for pending task
        try:
            session = engine._get(resolved_sid)
            pending = engine.store._get_pending_task(resolved_sid, result.agent_id)
            data["pending_task"] = pending if pending else None
        except Exception:
            data["pending_task"] = None
    except Exception as e:
        logger.warning("register_agent auto-advance failed: %s", e)
        data["auto_heartbeat"] = f"failed: {e}"
        data["pending_task"] = None

    return data


@mcp.tool()
def deregister_agent(session_id: str, agent_id: str) -> dict[str, Any]:
    """Deregister an agent from a session. The agent becomes inactive.

    Call this when user says /deregister or wants to leave a design discussion.
    The agent will be marked as inactive and will no longer be counted for phase completion.

    Args:
        session_id: The session identifier
        agent_id: The agent identifier to deregister

    Returns:
        Confirmation of deregistration
    """
    engine = _get_engine()
    logger.info("deregister_agent called: session_id=%r, agent_id=%r", session_id, agent_id)
    return engine.deregister_agent(session_id=session_id, agent_id=agent_id)


@mcp.tool()
def delete_session(session_id: str) -> dict[str, Any]:
    """Delete an archived session and all its data.

    Only archived sessions can be deleted. Active sessions must be archived first.

    Args:
        session_id: The session identifier to delete

    Returns:
        Confirmation of deletion
    """
    engine = _get_engine()
    logger.info("delete_session called: session_id=%r", session_id)
    return engine.delete_session(session_id=session_id)


@mcp.tool()
def submit_decision_points(
    session_id: str,
    agent_id: str,
    decision_points: list[dict],
) -> dict[str, Any]:
    """Submit decision points identified during Critic phase.

    Each decision point represents a key design divergence where agents disagree.
    Structure: [{topic, description, options: [{label, reasoning, pros, cons}], constraints}]

    Args:
        session_id: The session identifier
        agent_id: The submitting agent identifier
        decision_points: List of decision point dicts

    Returns:
        Confirmation with count and decision_ids
    """
    engine = _get_engine()
    return engine.submit_decision_points(session_id=session_id, agent_id=agent_id, decision_points=decision_points)


@mcp.tool()
def resolve_decision_point(
    session_id: str,
    decision_id: str,
    choice: str = "",
    custom: str = "",
) -> dict[str, Any]:
    """Resolve a decision point with human choice or custom input.

    Choose one of the proposed options, or provide a custom solution.

    Args:
        session_id: The session identifier
        decision_id: The decision point identifier
        choice: The option_id to select (from existing options)
        custom: Custom solution text (alternative to choice)

    Returns:
        Confirmation of resolution
    """
    engine = _get_engine()
    return engine.resolve_decision_point(session_id=session_id, decision_id=decision_id, choice=choice, custom=custom)


@mcp.tool()
def start_clarification(session_id: str) -> dict[str, Any]:
    """Start the clarification phase to refine a fuzzy requirement.

    The clarification phase has 4 sub-phases:
    1. CLARIFY_IDENTIFY - Each agent independently identifies assumptions (no peeking!)
    2. CLARIFY_REFINE - System merges assumptions; agents can supplement options
    3. CLARIFY_REVIEW - Human reviews and chooses from assumption options
    4. CLARIFY_REWRITE - Agents propose refined requirement; human approves one

    Requires at least 2 agents and a submitted requirement.

    Args:
        session_id: The session identifier

    Returns:
        Clarification start info with dimensions and instructions
    """
    engine = _get_engine()
    return engine.start_clarification(session_id)


@mcp.tool()
def submit_assumptions(
    session_id: str,
    agent_id: str,
    assumptions: list[dict],
) -> list[dict[str, Any]]:
    """Submit assumptions about the fuzzy requirement during CLARIFY_IDENTIFY phase.

    Each assumption should be organized by dimension and include alternatives for human to choose from.
    Do NOT read other agents' assumptions - submit independently to avoid anchoring bias.

    Assumption format:
    {
        "dimension": "core_entities|users_and_permissions|data_storage|core_workflow|non_functional|integration_and_boundary",
        "assumption": "Your assumed decision",
        "confidence": 0.7,
        "alternatives": [
            {"label": "Option A", "description": "Description of option A"},
            {"label": "Option B", "description": "Description of option B"}
        ],
        "rationale": "Why you made this assumption"
    }

    A "Other" option is automatically added if not present.

    Args:
        session_id: The session identifier
        agent_id: Your agent identifier
        assumptions: List of assumption objects (see format above)

    Returns:
        List of created assumptions
    """
    engine = _get_engine()
    created = engine.submit_assumptions(
        session_id=session_id,
        agent_id=agent_id,
        assumptions=assumptions,
    )
    return [a.model_dump() for a in created]


@mcp.tool()
def supplement_assumption_options(
    session_id: str,
    agent_id: str,
    supplements: list[dict],
) -> dict[str, str]:
    """Supplement alternatives to existing assumptions during CLARIFY_REFINE phase.

    You can add options to assumptions raised by other agents, but you CANNOT
    remove or challenge whether an assumption should exist.

    Supplement format:
    {
        "assumption_id": "id of the assumption to supplement",
        "label": "New option label",
        "description": "Description of the new option"
    }

    Args:
        session_id: The session identifier
        agent_id: Your agent identifier
        supplements: List of supplement objects (see format above)

    Returns:
        Confirmation
    """
    engine = _get_engine()
    engine.supplement_assumption_options(
        session_id=session_id,
        agent_id=agent_id,
        supplements=supplements,
    )
    return {"status": "supplemented", "count": str(len(supplements))}


@mcp.tool()
def get_merged_assumptions(session_id: str) -> list[dict[str, Any]]:
    """Get the merged assumption document after all agents have submitted.

    The system automatically merges similar assumptions and marks divergent ones
    (where agents disagree). Divergent assumptions require human resolution.

    Args:
        session_id: The session identifier

    Returns:
        List of merged assumption groups organized by dimension
    """
    engine = _get_engine()
    groups = engine.get_merged_assumptions(session_id)
    return [g.model_dump() for g in groups]


@mcp.tool()
def review_assumptions(
    session_id: str,
    choices: list[dict],
) -> dict[str, Any]:
    """Human reviews the merged assumption document and makes choices.

    For each assumption, choose one of the provided alternatives or "Other" for custom input.
    Divergent assumptions (where agents disagree) MUST be resolved.

    Choice format:
    {
        "assumption_id": "id of the assumption",
        "choice": "The label of the chosen alternative (or custom text for 'Other')"
    }

    Once all divergent assumptions are resolved, the session moves to CLARIFY_REWRITE.

    Args:
        session_id: The session identifier
        choices: List of choice objects (see format above)

    Returns:
        Review status
    """
    engine = _get_engine()
    engine.review_assumptions(session_id=session_id, choices=choices)
    session = _get_store().get_session(session_id)
    return {
        "status": "reviewed",
        "current_phase": session.current_phase.value if session else "unknown",
    }


@mcp.tool()
def submit_refined_requirement(
    session_id: str,
    agent_id: str,
    refined_statement: str,
    constraints: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
) -> dict[str, Any]:
    """Submit a refined requirement during CLARIFY_REWRITE phase.

    Based on the human's assumption choices, propose a clear, refined requirement
    that replaces the original fuzzy statement.

    Args:
        session_id: The session identifier
        agent_id: Your agent identifier
        refined_statement: The refined requirement statement
        constraints: Updated constraints based on assumption choices
        acceptance_criteria: Updated acceptance criteria

    Returns:
        The submitted refined requirement
    """
    engine = _get_engine()
    refined = engine.submit_refined_requirement(
        session_id=session_id,
        agent_id=agent_id,
        refined_statement=refined_statement,
        constraints=constraints,
        acceptance_criteria=acceptance_criteria,
    )
    return refined.model_dump()


@mcp.tool()
def approve_refined_requirement(
    session_id: str,
    refine_id: str,
) -> dict[str, Any]:
    """Human approves a refined requirement, replacing the original fuzzy statement.

    After approval, the session is ready for the formal debate phase.

    Args:
        session_id: The session identifier
        refine_id: The ID of the refined requirement to approve

    Returns:
        The approved requirement
    """
    engine = _get_engine()
    req = engine.approve_refined_requirement(session_id=session_id, refine_id=refine_id)
    return req.model_dump()


@mcp.tool()
def start_debate(session_id: str) -> dict[str, Any]:
    """Start the structured debate after clarification is complete.

    Each agent is assigned a random perspective for the Proposal phase.
    Perspectives rotate each round to ensure diversity of thought.

    The debate follows 6 phases per round:
    1. PROPOSAL - Each agent independently proposes from their assigned perspective
    2. CRITIC - Agents challenge each other's proposals (3+ risks, 2+ missing items)
    3. REVISION - Agents revise based on valid feedback (must show changes)
    4. OPTIMIZATION - Agents propose improvements
    5. DEVIL'S ADVOCATE - A designated agent argues the design will fail
    6. CONSENSUS - Agents vote on the final design

    Args:
        session_id: The session identifier

    Returns:
        Debate start info with assigned perspectives
    """
    engine = _get_engine()
    return engine.start_debate(session_id)


@mcp.tool()
def get_phase_context(session_id: str, agent_id: str) -> dict[str, Any]:
    """Get the current phase context for an agent. This is the PRIMARY way for agents to understand what to do next.

    The response varies by phase:
    - CLARIFY_IDENTIFY: Returns dimensions, your assumptions, submitted agents count
    - CLARIFY_REFINE: Returns merged assumptions for supplementing
    - CLARIFY_REVIEW: Returns merged assumptions and divergent items for human review
    - CLARIFY_REWRITE: Returns human choices and your refined requirement
    - PROPOSAL: Returns your assigned perspective, hides other proposals
    - CRITIC: Returns all proposals for this round
    - REVISION: Returns challenges against you
    - OPTIMIZATION: Returns all revisions
    - DEVIL'S ADVOCATE: Returns design summary, indicates if you're the DA
    - CONSENSUS: Returns design summary for voting

    Args:
        session_id: The session identifier
        agent_id: Your agent identifier

    Returns:
        Phase-specific context and instructions
    """
    engine = _get_engine()
    return engine.get_phase_context(session_id, agent_id)


@mcp.tool()
def submit_proposal(
    session_id: str,
    agent_id: str,
    architecture: str,
    tech_stack: str = "",
    tradeoffs: str = "",
    risks: str = "",
    assumptions: str = "",
    unknowns: str = "",
    raw_content: str = "",
) -> dict[str, Any]:
    """Submit a design proposal during the PROPOSAL phase.

    You are assigned a random perspective - use it to frame your proposal.
    IMPORTANT: Do NOT read other agents' proposals to avoid anchoring bias.

    Available perspectives: cost_efficiency, security_privacy, scalability,
    developer_experience, operational_stability, user_experience,
    data_integrity, integration_ecosystem

    Args:
        session_id: The session identifier
        agent_id: Your agent identifier
        architecture: Your proposed architecture design
        tech_stack: Recommended technology stack
        tradeoffs: Known tradeoffs in your proposal
        risks: Identified risks
        assumptions: Assumptions made in your proposal
        unknowns: Things you are uncertain about
        raw_content: Any additional free-form content for the proposal

    Returns:
        The submitted proposal
    """
    engine = _get_engine()
    proposal = engine.submit_proposal(
        session_id=session_id,
        agent_id=agent_id,
        architecture=architecture,
        tech_stack=tech_stack,
        tradeoffs=tradeoffs,
        risks=risks,
        assumptions=assumptions,
        unknowns=unknowns,
        raw_content=raw_content,
    )
    return proposal.model_dump()


@mcp.tool()
def submit_challenge(
    session_id: str,
    agent_id: str,
    target_agent_id: str,
    target_proposal_id: str,
    risks: list[str],
    missing_considerations: list[str],
    alternative_proposal: str = "",
    category: str = "architecture",
    priority: str = "medium",
    confidence: float = 0.5,
) -> dict[str, Any]:
    """Submit a challenge against another agent's proposal during the CRITIC phase.

    RULES: Vague agreement like 'I agree' or 'looks good' is FORBIDDEN.
    You MUST identify at least 3 risks, 2 missing considerations, and ideally 1 alternative.

    Args:
        session_id: The session identifier
        agent_id: Your agent identifier
        target_agent_id: The agent whose proposal you are challenging
        target_proposal_id: The proposal ID you are challenging
        risks: List of risks you identified (minimum 3 recommended)
        missing_considerations: List of missing considerations (minimum 2 recommended)
        alternative_proposal: Your alternative approach (recommended)
        category: Challenge category: architecture, scalability, maintainability, performance, deployment, observability, cost, security
        priority: Priority level: low, medium, high, critical
        confidence: Your confidence in this challenge (0.0 to 1.0)

    Returns:
        The submitted challenge
    """
    engine = _get_engine()
    challenge = engine.submit_challenge(
        session_id=session_id,
        agent_id=agent_id,
        target_agent_id=target_agent_id,
        target_proposal_id=target_proposal_id,
        risks=risks,
        missing_considerations=missing_considerations,
        alternative_proposal=alternative_proposal,
        category=category,
        priority=priority,
        confidence=confidence,
    )
    return challenge.model_dump()


@mcp.tool()
def submit_revision(
    session_id: str,
    agent_id: str,
    accepted_feedback: list[str],
    rejected_feedback: list[str],
    rejection_reasons: list[str],
    changed_design: str,
) -> dict[str, Any]:
    """Submit a design revision during the REVISION phase.

    RULES: Polite acknowledgment without design changes is FORBIDDEN.
    You MUST explicitly state what feedback you accepted/rejected and show concrete design changes.

    Args:
        session_id: The session identifier
        agent_id: Your agent identifier
        accepted_feedback: List of feedback items you accepted and incorporated
        rejected_feedback: List of feedback items you rejected
        rejection_reasons: Reasons for rejecting each item
        changed_design: Your revised design description showing concrete changes

    Returns:
        The submitted revision
    """
    engine = _get_engine()
    revision = engine.submit_revision(
        session_id=session_id,
        agent_id=agent_id,
        accepted_feedback=accepted_feedback,
        rejected_feedback=rejected_feedback,
        rejection_reasons=rejection_reasons,
        changed_design=changed_design,
    )
    return revision.model_dump()


@mcp.tool()
def submit_optimization(
    session_id: str,
    agent_id: str,
    description: str,
    impact: str = "",
    tradeoff: str = "",
    complexity_change: str = "",
) -> dict[str, Any]:
    """Submit an optimization suggestion during the OPTIMIZATION phase.

    Focus on making the design: simpler, more stable, cheaper, more maintainable, or more scalable.

    Args:
        session_id: The session identifier
        agent_id: Your agent identifier
        description: Description of the optimization
        impact: Expected impact of this optimization
        tradeoff: Tradeoff involved in this optimization
        complexity_change: How complexity changes (increased/decreased/neutral)

    Returns:
        The submitted optimization
    """
    engine = _get_engine()
    optimization = engine.submit_optimization(
        session_id=session_id,
        agent_id=agent_id,
        description=description,
        impact=impact,
        tradeoff=tradeoff,
        complexity_change=complexity_change,
    )
    return optimization.model_dump()


@mcp.tool()
def submit_devils_advocate(
    session_id: str,
    agent_id: str,
    failure_modes: list[str],
    risk_score: float = 0.5,
    mitigation: str = "",
) -> dict[str, Any]:
    """Submit a Devil's Advocate analysis during the DEVIL'S ADVOCATE phase.

    The designated agent must argue: "Assume this design will fail. Prove why."

    Args:
        session_id: The session identifier
        agent_id: Your agent identifier (must be the designated Devil's Advocate)
        failure_modes: List of potential failure modes for the current design
        risk_score: Overall risk score (0.0 = safe, 1.0 = certain failure)
        mitigation: Suggested mitigations for the identified failure modes

    Returns:
        The submitted Devil's Advocate analysis
    """
    engine = _get_engine()
    da = engine.submit_devils_advocate(
        session_id=session_id,
        agent_id=agent_id,
        failure_modes=failure_modes,
        risk_score=risk_score,
        mitigation=mitigation,
    )
    return da.model_dump()


@mcp.tool()
def cast_consensus_vote(
    session_id: str,
    agent_id: str,
    vote_type: str,
    comment: str = "",
) -> dict[str, Any]:
    """Cast a consensus vote during the CONSENSUS phase.

    When all agents agree, the session is automatically completed.
    If 2+ agents disagree or need clarification, the session moves to human review.

    Args:
        session_id: The session identifier
        agent_id: Your agent identifier
        vote_type: Your vote: agree, disagree, abstain, or needs_clarification
        comment: Optional explanation of your vote

    Returns:
        Vote confirmation and updated session status
    """
    engine = _get_engine()
    vote = engine.cast_consensus_vote(
        session_id=session_id,
        agent_id=agent_id,
        vote_type=VoteType(vote_type),
        comment=comment,
    )
    result = vote.model_dump()
    session = _get_store().get_session(session_id)
    if session:
        result["session_status"] = session.status.value
    return result


@mcp.tool()
def advance_phase(session_id: str) -> dict[str, Any]:
    """Manually advance the debate to the next phase.

    Phase order: clarify_identify -> clarify_refine -> clarify_review -> clarify_rewrite ->
    proposal -> critic -> revision -> optimization -> devils_advocate -> consensus

    Usually phases auto-advance when all agents submit. Use this only for manual override.

    Args:
        session_id: The session identifier

    Returns:
        Next phase information and instructions
    """
    engine = _get_engine()
    return engine.advance_phase(session_id)


@mcp.tool()
def advance_round(session_id: str) -> dict[str, Any]:
    """Advance to the next debate round (starts at CRITIC phase).

    Use this when a full 6-phase cycle is complete but consensus was not reached.
    If max rounds is reached, the session is automatically moved to human review.

    Args:
        session_id: The session identifier

    Returns:
        New round information
    """
    engine = _get_engine()
    return engine.advance_round(session_id)


@mcp.tool()
def raise_question(
    session_id: str,
    agent_id: str,
    question: str,
    options: list[dict] | None = None,
) -> dict[str, Any]:
    """Raise a pending question with suggested options for human to choose from.

    Agents should provide options whenever possible instead of asking open-ended questions.
    This minimizes human cognitive load - just pick an option instead of typing an answer.
    A "Other" option is automatically added for custom input.

    Option format: {"label": "Option name", "description": "What this option means"}

    Args:
        session_id: The session identifier
        agent_id: Your agent identifier
        question: The question that needs user clarification
        options: Suggested options for the user to choose from (recommended)

    Returns:
        The pending question with options
    """
    engine = _get_engine()
    pq = engine.raise_question(
        session_id=session_id,
        agent_id=agent_id,
        question=question,
        options=options,
    )
    return pq.model_dump()


@mcp.tool()
def resolve_question(session_id: str, question_id: str, choice: str) -> dict[str, str]:
    """Resolve a pending question by choosing one of the provided options or entering custom text.

    Args:
        session_id: The session identifier
        question_id: The question identifier to resolve
        choice: The chosen option label or custom text (for "Other" option)

    Returns:
        Confirmation of resolution
    """
    engine = _get_engine()
    engine.resolve_question(session_id, question_id, choice)
    return {"status": "resolved", "question_id": question_id, "choice": choice}


@mcp.tool()
def get_pending_questions(session_id: str) -> list[dict[str, Any]]:
    """Get all unresolved questions in a session that need user clarification.

    Each question includes suggested options - just pick one instead of typing.

    Args:
        session_id: The session identifier

    Returns:
        List of unresolved questions with options
    """
    engine = _get_engine()
    questions = engine.get_pending_questions(session_id)
    return [q.model_dump() for q in questions]


@mcp.tool()
def request_human_review(session_id: str, reason: str) -> dict[str, str]:
    """Request human review when agents cannot reach consensus.

    Args:
        session_id: The session identifier
        reason: Why human review is needed

    Returns:
        Confirmation
    """
    engine = _get_engine()
    engine.request_human_review(session_id, reason)
    return {"status": "human_review_requested", "session_id": session_id}


@mcp.tool()
def human_approve(session_id: str, approver: str, comment: str = "") -> dict[str, str]:
    """Approve the session as a human reviewer, marking it as completed.

    Args:
        session_id: The session identifier
        approver: Name/identifier of the human approver
        comment: Optional approval comment

    Returns:
        Confirmation
    """
    engine = _get_engine()
    engine.human_approve(session_id, approver, comment)
    return {"status": "approved", "session_id": session_id}


@mcp.tool()
def human_reject(session_id: str, approver: str, reason: str) -> dict[str, str]:
    """Reject the session, returning it to CRITIC phase for more discussion.

    Args:
        session_id: The session identifier
        approver: Name/identifier of the human reviewer
        reason: Why the session is being rejected

    Returns:
        Confirmation
    """
    engine = _get_engine()
    engine.human_reject(session_id, approver, reason)
    return {"status": "rejected_back_to_discussion", "session_id": session_id}


@mcp.tool()
def human_override(session_id: str, approver: str, decision: str, rationale: str) -> dict[str, str]:
    """Override agent consensus with a human decision. Session is marked as completed.

    Use this when you want to make a final decision that overrides the agent debate.

    Args:
        session_id: The session identifier
        approver: Name/identifier of the human decision maker
        decision: The final decision
        rationale: Why this decision overrides the agent debate

    Returns:
        Confirmation
    """
    engine = _get_engine()
    engine.human_override(session_id, approver, decision, rationale)
    return {"status": "overridden", "session_id": session_id}


@mcp.tool()
def archive_session(session_id: str) -> dict[str, Any]:
    """Archive a completed session. Working data (requirements, docs, history) is cleaned up
    and moved to the archive directory. The session record is preserved.

    Use this after the design document has been generated and approved to prepare
    the workspace for the next discussion.

    Args:
        session_id: The session identifier (must be completed)

    Returns:
        Archive info including path
    """
    engine = _get_engine()
    return engine.archive_session(session_id)


@mcp.tool()
def force_skip_clarification(session_id: str) -> dict[str, Any]:
    """Force skip the clarification phase and go directly to the debate (PROPOSAL) phase.

    Use this when:
    - The requirement is already very detailed and clear
    - Agents agree that clarification is unnecessary
    - You want to override the system's clarity assessment

    Can only be called during clarification sub-phases (CLARIFY_IDENTIFY through CLARIFY_REWRITE).

    Args:
        session_id: The session identifier

    Returns:
        Info about the skip action and the PROPOSAL phase start
    """
    engine = _get_engine()
    return engine.force_skip_clarification(session_id)


@mcp.tool()
def heartbeat(session_id: str, agent_id: str) -> dict[str, Any]:
    """Send a heartbeat to indicate the agent is still active.

    Agents should call this periodically (e.g., every 60 seconds) during long-running
    operations to prevent being marked as inactive. An agent is considered inactive
    if no heartbeat or submission is received within 5 minutes (300 seconds).

    Inactive agents are excluded from phase completion checks, allowing the session
    to continue with remaining active agents.

    Args:
        session_id: The session identifier
        agent_id: Your agent identifier

    Returns:
        Heartbeat acknowledgment with current session state
    """
    engine = _get_engine()
    return engine.heartbeat(session_id, agent_id)


@mcp.tool()
def wait_for_task(session_id: str, agent_id: str, timeout: int = 300) -> dict[str, Any]:
    """Blocking pull: wait for the next task assigned to this agent.

    This is the CORE protocol of the system. Instead of polling or being pushed,
    agents block-wait for tasks. The server assigns tasks based on the current
    phase and round.

    Call this after registering, and after submitting each result. The server
    will return the next task when it's ready, or None on timeout.

    IMPORTANT: During wait phases (clarify_review, human_review), keep calling
    this with a reasonable timeout to maintain your heartbeat.

    Args:
        session_id: The session identifier
        agent_id: Your agent identifier
        timeout: Maximum seconds to wait (default: 300, max: 600)

    Returns:
        Task dict with keys: task_id, task_type, phase, round_number, payload
        Or {"status": "timeout"} if no task available within timeout
    """
    engine = _get_engine()
    actual_timeout = min(max(timeout, 1), 600)
    task = engine.wait_for_task_engine(session_id, agent_id, timeout=float(actual_timeout))
    if task is None:
        return {"status": "timeout"}
    return task


@mcp.tool()
def submit_result(session_id: str, agent_id: str, task_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """Submit the result of a task and get the next task.

    This is the unified submission interface. After completing a task obtained
    from wait_for_task, submit the result here. The system will:
    1. Record the result as an artifact
    2. Mark the task as completed
    3. Check if the phase is complete
    4. Return the next task if available

    The result dict should contain the artifact data specific to the task_type:
    - submit_assumptions: {"assumptions": [...]}
    - submit_proposal: {"architecture": "...", ...}
    - submit_challenge: {"risks": [...], ...}
    - submit_revision: {"changed_design": "...", ...}
    - submit_optimization: {"description": "...", ...}
    - submit_devils_advocate: {"failure_modes": [...], ...}
    - cast_consensus_vote: {"vote_type": "agree", ...}

    IMPORTANT: The result dict MUST include "_task_type" key matching the task_type
    from wait_for_task, so the system knows which submission method to dispatch to.

    Args:
        session_id: The session identifier
        agent_id: Your agent identifier
        task_id: The task_id from wait_for_task
        result: The result data dict (must include "_task_type")

    Returns:
        The next task dict, or {"status": "no_task"} if waiting
    """
    engine = _get_engine()
    return engine.submit_result_engine(session_id, agent_id, task_id, result)


@mcp.tool()
def check_stalled(session_id: str) -> dict[str, Any]:
    """Check if a session is stalled due to inactive agents and attempt recovery.

    This tool detects agents that have been inactive for more than 5 minutes
    (no heartbeat or submission) and marks them as inactive. If enough active
    agents remain (>=2), the session can auto-advance past the stalled phase.

    Call this when:
    - A session seems stuck with no progress
    - You suspect an agent has disconnected
    - You want to check agent health status

    Args:
        session_id: The session identifier

    Returns:
        Stalled check results including inactive agents and recovery status
    """
    engine = _get_engine()
    return engine.check_stalled(session_id)


@mcp.tool()
def add_requirement_delta(
    session_id: str,
    delta_statement: str,
    constraints: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
) -> dict[str, Any]:
    """Add a supplementary requirement (delta) to an existing session.

    Use this when you have an existing detailed design document and want to add
    a new fuzzy requirement on top of it. For example, your session already has
    a detailed architecture document, and now you want to add "I want a diary feature".

    The system will:
    1. Evaluate the delta's clarity independently
    2. If the delta is fuzzy but the base requirement is clear, only clarify the delta
    3. If the delta is clear enough, skip clarification and go to PROPOSAL
    4. The debate will cover the delta in context of the existing design

    Can only be called on a session that has a requirement already submitted.
    If the session is in PROPOSAL or later debate phase, the delta is appended
    and the debate continues from the current phase.

    Args:
        session_id: The session identifier
        delta_statement: The supplementary requirement statement (can be fuzzy)
        constraints: Additional constraints for this delta
        acceptance_criteria: Additional acceptance criteria for this delta

    Returns:
        Updated requirement info with clarity assessment
    """
    engine = _get_engine()
    return engine.add_requirement_delta(
        session_id=session_id,
        delta_statement=delta_statement,
        constraints=constraints or [],
        acceptance_criteria=acceptance_criteria or [],
    )


@mcp.tool()
def generate_design_document(session_id: str) -> str:
    """Generate a structured design document from the completed debate.

    Call this after the session is completed (consensus reached or human approved).
    Generates 4 output documents: design document, ADR, debate summary, and human decision points.

    Args:
        session_id: The session identifier

    Returns:
        The generated design document content
    """
    store = _get_store()
    session = store.get_session(session_id)
    if session is None:
        return f"Session '{session_id}' not found."
    if session.status not in (SessionStatus.COMPLETED, SessionStatus.HUMAN_REVIEW):
        return f"Session is in '{session.status.value}' status. Please complete the debate before generating the design document."
    return _generate_design_document(session)


@mcp.resource("designdoc://sessions")
def list_sessions_resource() -> str:
    """List all sessions as a resource."""
    store = _get_store()
    sessions = store.list_sessions()
    if not sessions:
        return "No sessions found. Create one via the Web UI at http://localhost:8765"
    active = [s for s in sessions if s.status.value not in ("archived", "completed")]
    lines = []
    if active:
        lines.append("== Active Sessions ==")
        for s in active:
            agents_str = ", ".join(a.name for a in s.agents) if s.agents else "none"
            req_status = "has requirement" if s.requirement else "no requirement"
            lines.append(f"- {s.session_id}: {s.title} [{s.status.value}] Phase: {s.current_phase.value} | {req_status} | Agents: {agents_str}")
            lines.append(f"  -> Register: /register {s.session_id}")
        if len(active) == 1:
            lines.append("")
            lines.append(f"Only one active session. You can register directly: /register {active[0].session_id}")
    archived = [s for s in sessions if s.status.value in ("archived", "completed")]
    if archived:
        lines.append("")
        lines.append(f"== {len(archived)} archived/completed session(s) (hidden) ==")
    return "\n".join(lines)


@mcp.resource("designdoc://active-session")
def active_session_resource() -> str:
    """Get the single active session info for quick registration."""
    store = _get_store()
    sessions = store.list_sessions()
    active = [s for s in sessions if s.status.value not in ("archived", "completed")]
    if not active:
        return "No active sessions. Create one via the Web UI at http://localhost:8765"
    if len(active) == 1:
        s = active[0]
        agents_str = ", ".join(a.name for a in s.agents) if s.agents else "none"
        req_status = "has requirement" if s.requirement else "no requirement"
        return (
            f"Active Session: {s.session_id}\n"
            f"Title: {s.title}\n"
            f"Status: {s.status.value} | Phase: {s.current_phase.value} | Round: {s.current_round}\n"
            f"Requirement: {req_status}\n"
            f"Agents: {agents_str}\n"
            f"\nRegister now: /register {s.session_id}"
        )
    return f"Multiple active sessions ({len(active)}). Use /register to see and choose, or check designdoc://sessions for details."


@mcp.resource("designdoc://session/{session_id}")
def get_session_resource(session_id: str) -> str:
    """Get session details as a resource."""
    store = _get_store()
    session = store.get_session(session_id)
    if session is None:
        return f"Session '{session_id}' not found."
    return _generate_design_document(session)


@mcp.prompt()
def designdoc_guide() -> str:
    """Get the DesignDoc MCP collaboration guide. Call this when you first connect to understand how to participate."""
    store = _get_store()
    sessions = store.list_sessions()
    active = [s for s in sessions if s.status.value not in ("archived", "completed")]

    guide = """# DesignDoc MCP Collaboration Guide

You are connected to a DesignDoc MCP server for multi-agent design document collaboration.

**CRITICAL**: You are a CLIENT of this MCP server, NOT its developer.
- Do NOT read or modify the project source code (`src/`, `server.py`, `engine.py`, etc.)
- Do NOT implement any logic yourself — all collaboration logic is handled by the MCP server
- Do NOT try to manually advance phases — the system does this automatically when all agents submit
- Your ONLY job is to CALL the MCP tools listed below
- Any MCP client can participate — you do NOT need to be running inside a specific IDE

## Quick Start
1. Check active sessions: read resource `designdoc://active-session`
2. Register to a session: call MCP tool `register_agent` with no parameters (auto-detects session and your info)
3. Save the returned `session_id` and `agent_id`
4. Each time you are prompted:
   - Call MCP tool `heartbeat(session_id, agent_id)`
   - Call MCP tool `get_phase_context(session_id, agent_id)`
   - Submit content for the current phase using the appropriate MCP tool

**IMPORTANT**: During "wait" phases (clarify_review, human_review), you MUST still call `heartbeat` periodically (every 2-3 minutes) to prevent being marked as inactive (5-minute timeout). When the phase changes, `get_phase_context` will return the new phase.

## Commands
- `/register` - Register to a session (auto-detects session and your info)
- `/deregister` - Leave the current session

## Phase Actions
| Phase | Your Action |
|-------|-------------|
| clarify_identify | submit_assumptions (independent, no peeking) |
| clarify_refine | supplement_assumption_options |
| clarify_review | Wait for human |
| clarify_rewrite | submit_refined_requirement |
| proposal | submit_proposal (from assigned perspective, no peeking) |
| critic | submit_challenge (3+ risks, 2+ missing, no polite agreement) |
| revision | submit_revision (must show changes) |
| optimization | submit_optimization |
| devils_advocate | submit_devils_advocate (if designated) |
| consensus | cast_consensus_vote |
| human_review | Wait for human |
"""
    if not active:
        guide += "\n## Current Status\nNo active sessions. Ask the user to create one via the Web UI at http://localhost:8765"
    elif len(active) == 1:
        s = active[0]
        guide += f"\n## Current Status\nOne active session: **{s.session_id}** ({s.title})\nStatus: {s.status.value} | Phase: {s.current_phase.value}\nRegister now: `/register {s.session_id}`"
    else:
        guide += f"\n## Current Status\n{len(active)} active sessions. Read `designdoc://sessions` to see them all."
    return guide


def main() -> None:
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="DesignDoc MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "http", "streamable-http"],
        default=os.environ.get("DESIGNDOC_TRANSPORT", "stdio"),
        help="Transport protocol (default: stdio, or DESIGNDOC_TRANSPORT env)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("DESIGNDOC_HOST", "0.0.0.0"),
        help="Host for SSE/HTTP transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("DESIGNDOC_PORT", "8765")),
        help="Port for SSE/HTTP transport (default: 8765)",
    )
    parser.add_argument(
        "--no-web",
        action="store_true",
        default=os.environ.get("DESIGNDOC_NO_WEB", "") == "1",
        help="Disable web UI (only MCP endpoints)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        import logging
        from contextlib import asynccontextmanager, AsyncExitStack

        from starlette.applications import Starlette
        from starlette.routing import Mount

        from .web import web_app

        sse_app = mcp.http_app(transport="sse")
        http_app = mcp.http_app(transport="http", stateless_http=True)

        routes = list(sse_app.routes) + list(http_app.routes)

        if not args.no_web:
            routes.append(Mount("/", app=web_app))

        @asynccontextmanager
        async def combined_lifespan(app):
            async with AsyncExitStack() as stack:
                await stack.enter_async_context(sse_app.lifespan(app))
                await stack.enter_async_context(http_app.lifespan(app))
                yield

        app = Starlette(routes=routes, lifespan=combined_lifespan)

        log_dir = os.environ.get("DESIGNDOC_LOG_DIR", "")
        if not log_dir:
            log_dir = str(Path(__file__).resolve().parent.parent.parent / "logs")
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # 主日志
        main_handler = logging.FileHandler(log_path / "designdoc_mcp.log", encoding="utf-8")
        main_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        main_handler.addFilter(lambda r: not r.name.startswith("designdoc_mcp.heartbeat"))
        logging.getLogger().addHandler(main_handler)

        # 心跳日志（单独文件）
        hb_handler = logging.FileHandler(log_path / "heartbeat.log", encoding="utf-8")
        hb_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        hb_logger = logging.getLogger("designdoc_mcp.heartbeat")
        hb_logger.addHandler(hb_handler)
        hb_logger.propagate = False  # 不传播到根 logger

        logging.getLogger("uvicorn").addHandler(main_handler)
        logging.getLogger("uvicorn.access").addHandler(main_handler)
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("DesignDoc MCP server starting - logs: %s", log_path)
        logger.info("MCP endpoints: SSE=GET /sse + POST /messages, StreamableHTTP=POST /mcp")

        import signal

        config = uvicorn.Config(app, host=args.host, port=args.port, timeout_graceful_shutdown=1)
        server = uvicorn.Server(config)

        def _force_quit(sig, frame):
            raise SystemExit(0)

        signal.signal(signal.SIGINT, _force_quit)
        try:
            server.run()
        except (KeyboardInterrupt, SystemExit):
            logger.info("DesignDoc MCP server stopped")


if __name__ == "__main__":
    main()
