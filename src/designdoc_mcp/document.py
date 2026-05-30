from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    ASSUMPTION_DIMENSIONS,
    DIMENSION_DESCRIPTIONS,
    PERSPECTIVE_DESCRIPTIONS,
    Challenge,
    DevilsAdvocate,
    MergedAssumptionGroup,
    Optimization,
    Proposal,
    RefinedRequirement,
    Revision,
    Session,
    SessionStatus,
    VoteType,
)


def generate_design_document(session: Session) -> str:
    lines: list[str] = []
    _add_header(lines, session)
    _add_overview(lines, session)
    _add_requirement(lines, session)
    _add_goals_and_constraints(lines, session)
    _add_assumption_decisions(lines, session)
    _add_final_architecture(lines, session)
    _add_technical_decisions(lines, session)
    _add_data_model_and_api(lines, session)
    _add_risks_and_mitigations(lines, session)
    _add_implementation_plan(lines, session)
    _add_acceptance_criteria(lines, session)
    return "\n".join(lines)


def generate_adr(session: Session) -> str:
    lines: list[str] = []
    lines.append(f"# Architecture Decision Records: {session.title}")
    lines.append(f"")
    lines.append(f"> Session: {session.session_id}")
    lines.append(f"> Date: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"")

    decisions = _extract_decisions(session)
    for i, decision in enumerate(decisions, 1):
        lines.append(f"## ADR-{i:03d}: {decision['title']}")
        lines.append(f"")
        lines.append(f"### Decision")
        lines.append(f"")
        lines.append(decision["decision"])
        lines.append(f"")
        lines.append(f"### Alternatives Considered")
        lines.append(f"")
        for alt in decision.get("alternatives", []):
            lines.append(f"- {alt}")
        lines.append(f"")
        lines.append(f"### Tradeoffs")
        lines.append(f"")
        lines.append(decision.get("tradeoffs", "N/A"))
        lines.append(f"")
        lines.append(f"### Rationale")
        lines.append(f"")
        lines.append(decision.get("rationale", "Based on multi-agent debate consensus"))
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    return "\n".join(lines)


def generate_debate_summary(session: Session) -> str:
    lines: list[str] = []
    lines.append(f"# Debate Summary: {session.title}")
    lines.append(f"")
    lines.append(f"> Session: {session.session_id}")
    lines.append(f"> Rounds: {session.current_round}")
    lines.append(f"> Status: {session.status.value}")
    lines.append(f"")

    _add_clarification_summary(lines, session)
    _add_major_challenges(lines, session)
    _add_resolved_risks(lines, session)
    _add_key_improvements(lines, session)
    _add_event_timeline(lines, session)

    return "\n".join(lines)


def generate_human_decision_points(session: Session) -> str:
    lines: list[str] = []
    lines.append(f"# Human Decision Points: {session.title}")
    lines.append(f"")
    lines.append(f"> Session: {session.session_id}")
    lines.append(f"")

    _add_assumption_choices_summary(lines, session)

    unresolved = [q for q in session.pending_questions if not q.resolved]
    if unresolved:
        lines.append(f"## Unresolved Questions Requiring User Input")
        lines.append(f"")
        for i, q in enumerate(unresolved, 1):
            lines.append(f"{i}. **{q.question}** (asked by {q.asked_by})")
            if q.options:
                for opt in q.options:
                    lines.append(f"   - {opt.label}: {opt.description}")
        lines.append(f"")

    disputed_votes = [v for v in session.consensus_votes if v.vote_type in (VoteType.DISAGREE, VoteType.NEEDS_CLARIFICATION)]
    if disputed_votes:
        lines.append(f"## Disputed Decisions")
        lines.append(f"")
        for v in disputed_votes:
            lines.append(f"- **{v.agent_id}**: {v.vote_type.value} - {v.comment or 'No comment'}")
        lines.append(f"")

    high_risk_das = [da for da in session.devils_advocates if da.risk_score >= 0.7]
    if high_risk_das:
        lines.append(f"## High-Risk Failure Modes")
        lines.append(f"")
        for da in high_risk_das:
            lines.append(f"### Devil's Advocate: {_agent_name(session, da.agent_id)} (Risk Score: {da.risk_score})")
            lines.append(f"")
            for fm in da.failure_modes:
                lines.append(f"- {fm}")
            if da.mitigation:
                lines.append(f"")
                lines.append(f"**Mitigation**: {da.mitigation}")
            lines.append(f"")

    if session.status == SessionStatus.HUMAN_REVIEW:
        reason = session.metadata.get("human_review_reason", "No reason specified")
        lines.append(f"## Review Required")
        lines.append(f"")
        lines.append(f"**Reason**: {reason}")
        lines.append(f"")
        lines.append(f"### Available Actions")
        lines.append(f"- `human_approve`: Approve the design and mark session as completed")
        lines.append(f"- `human_reject`: Reject and send back for more discussion")
        lines.append(f"- `human_override`: Make a final decision overriding agent consensus")
        lines.append(f"")

    return "\n".join(lines)


def generate_full_output(session: Session) -> dict[str, str]:
    return {
        "design_document": generate_design_document(session),
        "adr": generate_adr(session),
        "debate_summary": generate_debate_summary(session),
        "human_decision_points": generate_human_decision_points(session),
    }


import json as _json


def generate_design_document_json(session: Session) -> str:
    """Generate a structured JSON design document from the session."""
    data = {
        "session_id": session.session_id,
        "title": session.title,
        "description": session.description,
        "status": session.status.value,
        "phase": session.current_phase.value,
        "round": session.current_round,
        "clarify_round": session.clarify_round,
        "requirement": session.requirement.model_dump() if session.requirement else None,
        "agents": [a.model_dump() for a in session.agents],
        "assumptions": [a.model_dump() for a in session.assumptions],
        "merged_assumptions": [g.model_dump() for g in session.merged_assumptions],
        "refined_requirements": [r.model_dump() for r in session.refined_requirements],
        "proposals": [p.model_dump() for p in session.proposals],
        "challenges": [c.model_dump() for c in session.challenges],
        "revisions": [rv.model_dump() for rv in session.revisions],
        "optimizations": [o.model_dump() for o in session.optimizations],
        "devils_advocates": [d.model_dump() for d in session.devils_advocates],
        "consensus_votes": [v.model_dump() for v in session.consensus_votes],
        "human_votes": [hv.model_dump() for hv in session.human_votes],
        "decision_points": [dp.model_dump() for dp in session.decision_points],
        "requirement_deltas": [d.model_dump() for d in session.requirement_deltas],
        "pending_questions": [q.model_dump() for q in session.pending_questions],
        "events_count": len(session.events),
    }
    return _json.dumps(data, indent=2, default=str)


def generate_design_document_html(session: Session) -> str:
    """Generate a basic HTML design document from the session."""
    md = generate_design_document(session)
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="UTF-8">',
        f"  <title>{session.title}</title>",
        "  <style>",
        "    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }",
        "    h1, h2, h3 { color: #333; }",
        "    table { border-collapse: collapse; width: 100%; }",
        "    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
        "    th { background: #f5f5f5; }",
        "    code { background: #f4f4f4; padding: 2px 6px; border-radius: 4px; }",
        "    blockquote { border-left: 4px solid #ddd; margin: 0; padding-left: 16px; color: #666; }",
        "  </style>",
        "</head>",
        "<body>",
    ]
    # Convert markdown headers to HTML
    for raw in md.splitlines():
        line = raw
        # Headers
        if line.startswith("# "):
            line = f"<h1>{line[2:]}</h1>"
        elif line.startswith("## "):
            line = f"<h2>{line[3:]}</h2>"
        elif line.startswith("### "):
            line = f"<h3>{line[4:]}</h3>"
        elif line.startswith("> "):
            line = f"<blockquote>{line[2:]}</blockquote>"
        elif line.startswith("- "):
            line = f"<li>{line[2:]}</li>"
        elif line.startswith("| ") and line.endswith(" |"):
            # Table rows handled below
            pass
        elif line == "":
            line = "<br>"
        else:
            line = f"<p>{line}</p>"
        lines.append(line)
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines)


def _add_header(lines: list[str], session: Session) -> None:
    lines.append(f"# {session.title}")
    lines.append(f"")
    lines.append(f"> Design Document generated by DesignDoc MCP Collaboration System")
    lines.append(f"> Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"> Session ID: {session.session_id}")
    lines.append(f"> Debate Rounds: {session.current_round}")
    participants = ", ".join(a.name for a in session.agents)
    lines.append(f"> Participants: {participants}")
    if session.requirement and session.requirement.is_refined:
        lines.append(f"> Requirement: Refined (original was fuzzy)")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")


def _add_overview(lines: list[str], session: Session) -> None:
    lines.append(f"## Overview")
    lines.append(f"")
    lines.append(session.description)
    lines.append(f"")
    if session.agents:
        lines.append(f"### Participating Agents")
        lines.append(f"")
        lines.append(f"| Agent | Model | Provider | Perspective |")
        lines.append(f"|-------|-------|----------|-------------|")
        for a in session.agents:
            model_str = a.model or "-"
            provider_str = a.provider or "-"
            perspective_str = a.current_perspective or "-"
            lines.append(f"| {a.name} | {model_str} | {provider_str} | {perspective_str} |")
        lines.append(f"")


def _add_requirement(lines: list[str], session: Session) -> None:
    if not session.requirement:
        return
    lines.append(f"## Requirement")
    lines.append(f"")
    if session.requirement.is_refined and session.requirement.original_statement:
        lines.append(f"### Original (Fuzzy) Requirement")
        lines.append(f"")
        lines.append(f"> {session.requirement.original_statement}")
        lines.append(f"")
        lines.append(f"### Refined Requirement")
        lines.append(f"")
    lines.append(session.requirement.problem_statement)
    lines.append(f"")


def _add_goals_and_constraints(lines: list[str], session: Session) -> None:
    if not session.requirement:
        return
    has_content = False

    if session.requirement.acceptance_criteria:
        has_content = True
        lines.append(f"### Acceptance Criteria")
        lines.append(f"")
        for ac in session.requirement.acceptance_criteria:
            lines.append(f"- [ ] {ac}")
        lines.append(f"")

    if session.requirement.constraints:
        has_content = True
        lines.append(f"### Constraints")
        lines.append(f"")
        for c in session.requirement.constraints:
            lines.append(f"- {c}")
        lines.append(f"")

    if session.requirement.tech_preferences:
        has_content = True
        lines.append(f"### Tech Preferences")
        lines.append(f"")
        for t in session.requirement.tech_preferences:
            lines.append(f"- {t}")
        lines.append(f"")

    if session.requirement.forbidden_items:
        has_content = True
        lines.append(f"### Forbidden")
        lines.append(f"")
        for f in session.requirement.forbidden_items:
            lines.append(f"- {f}")
        lines.append(f"")

    if has_content:
        lines.append("")


def _add_assumption_decisions(lines: list[str], session: Session) -> None:
    if not session.merged_assumptions:
        return

    resolved_assumptions = []
    for group in session.merged_assumptions:
        for a in group.assumptions:
            if a.human_choice:
                resolved_assumptions.append((group.dimension, a))

    if not resolved_assumptions:
        return

    lines.append(f"## Assumption Decisions (from Clarification Phase)")
    lines.append(f"")
    lines.append(f"The following assumptions were identified and resolved during the clarification phase:")
    lines.append(f"")

    current_dim = ""
    for dim, a in resolved_assumptions:
        if dim != current_dim:
            current_dim = dim
            dim_desc = DIMENSION_DESCRIPTIONS.get(dim, dim)
            lines.append(f"### {dim.replace('_', ' ').title()} ({dim_desc})")
            lines.append(f"")
        lines.append(f"- **{a.assumption}** → Chose: *{a.human_choice}*")
        if a.rationale:
            lines.append(f"  Rationale: {a.rationale}")
    lines.append(f"")


def _add_final_architecture(lines: list[str], session: Session) -> None:
    lines.append(f"## Final Architecture")
    lines.append(f"")

    latest_proposals = _get_latest_proposals(session)
    latest_revisions = _get_latest_revisions(session)

    if latest_revisions:
        for r in latest_revisions:
            agent_name = _agent_name(session, r.agent_id)
            perspective = _get_agent_perspective(session, r.agent_id, r.round_number)
            lines.append(f"### Revised Design by {agent_name}")
            if perspective:
                lines.append(f"*Perspective: {PERSPECTIVE_DESCRIPTIONS.get(perspective, perspective)}*")
            lines.append(f"")
            lines.append(r.changed_design)
            lines.append(f"")
    elif latest_proposals:
        for p in latest_proposals:
            agent_name = _agent_name(session, p.agent_id)
            perspective = p.perspective
            lines.append(f"### Proposal by {agent_name}")
            if perspective:
                lines.append(f"*Perspective: {PERSPECTIVE_DESCRIPTIONS.get(perspective, perspective)}*")
            lines.append(f"")
            if p.architecture:
                lines.append(p.architecture)
            elif p.raw_content:
                lines.append(p.raw_content)
            lines.append(f"")
    else:
        lines.append(f"*待辩论完成后生成。*")
        lines.append(f"")


def _add_technical_decisions(lines: list[str], session: Session) -> None:
    lines.append(f"## Technical Decisions")
    lines.append(f"")

    proposals = _get_latest_proposals(session)
    for p in proposals:
        if p.tech_stack:
            agent_name = _agent_name(session, p.agent_id)
            lines.append(f"### Tech Stack ({agent_name})")
            lines.append(f"")
            lines.append(p.tech_stack)
            lines.append(f"")

    optimizations = _get_latest_optimizations(session)
    if optimizations:
        lines.append(f"### Optimizations")
        lines.append(f"")
        for o in optimizations:
            agent_name = _agent_name(session, o.agent_id)
            lines.append(f"**{agent_name}**: {o.description}")
            if o.impact:
                lines.append(f"- Impact: {o.impact}")
            if o.tradeoff:
                lines.append(f"- Tradeoff: {o.tradeoff}")
            lines.append(f"")


def _add_data_model_and_api(lines: list[str], session: Session) -> None:
    lines.append(f"## Data Model & API Design")
    lines.append(f"")
    lines.append(f"*To be refined during implementation based on the architecture above.*")
    lines.append(f"")


def _add_risks_and_mitigations(lines: list[str], session: Session) -> None:
    lines.append(f"## Risks & Mitigations")
    lines.append(f"")

    all_risks: list[tuple[str, str]] = []
    for p in _get_latest_proposals(session):
        if p.risks:
            all_risks.append((_agent_name(session, p.agent_id), p.risks))

    for c in session.challenges:
        for risk in c.risks:
            all_risks.append((_agent_name(session, c.agent_id), risk))

    for da in session.devils_advocates:
        for fm in da.failure_modes:
            all_risks.append((f"Devil's Advocate ({_agent_name(session, da.agent_id)})", fm))

    if all_risks:
        seen = set()
        for source, risk in all_risks:
            key = risk[:80]
            if key not in seen:
                seen.add(key)
                lines.append(f"- **[{source}]** {risk}")
        lines.append(f"")
    else:
        lines.append(f"No significant risks identified.")
        lines.append(f"")


def _add_implementation_plan(lines: list[str], session: Session) -> None:
    lines.append(f"## Implementation Plan")
    lines.append(f"")
    lines.append(f"*Implementation will be carried out by a single agent based on this design document.*")
    lines.append(f"")


def _add_acceptance_criteria(lines: list[str], session: Session) -> None:
    if not session.requirement or not session.requirement.acceptance_criteria:
        return
    lines.append(f"## Acceptance Criteria")
    lines.append(f"")
    for ac in session.requirement.acceptance_criteria:
        lines.append(f"- [ ] {ac}")
    lines.append(f"")


def _add_clarification_summary(lines: list[str], session: Session) -> None:
    if not session.assumptions and not session.merged_assumptions:
        return

    lines.append(f"## Clarification Phase Summary")
    lines.append(f"")

    if session.requirement and session.requirement.original_statement:
        lines.append(f"**Original Requirement**: {session.requirement.original_statement}")
        lines.append(f"")

    total_assumptions = len(session.assumptions)
    divergent_count = sum(1 for g in session.merged_assumptions if g.divergent)
    resolved_count = sum(1 for g in session.merged_assumptions for a in g.assumptions if a.human_choice)

    lines.append(f"- Total assumptions identified: {total_assumptions}")
    lines.append(f"- Divergent assumptions (agents disagreed): {divergent_count}")
    lines.append(f"- Assumptions resolved by human: {resolved_count}")
    lines.append(f"")

    if session.refined_requirements:
        lines.append(f"**Refined Requirement Submitted**: Yes ({len(session.refined_requirements)} version(s))")
        lines.append(f"")


def _add_assumption_choices_summary(lines: list[str], session: Session) -> None:
    if not session.merged_assumptions:
        return

    divergent = [g for g in session.merged_assumptions if g.divergent]
    if not divergent:
        return

    lines.append(f"## Divergent Assumption Resolutions")
    lines.append(f"")
    lines.append(f"The following assumptions had agent disagreement and required human resolution:")
    lines.append(f"")

    for group in divergent:
        dim_name = group.dimension.replace("_", " ").title()
        lines.append(f"### {dim_name}")
        lines.append(f"")
        for a in group.assumptions:
            lines.append(f"- **{a.assumption}** (by {_agent_name(session, a.agent_id)})")
            if a.human_choice:
                lines.append(f"  → Human chose: *{a.human_choice}*")
            else:
                lines.append(f"  → **UNRESOLVED**")
        lines.append(f"")


def _add_major_challenges(lines: list[str], session: Session) -> None:
    if not session.challenges:
        return
    lines.append(f"## Major Challenges Raised")
    lines.append(f"")
    for c in session.challenges:
        source = _agent_name(session, c.agent_id)
        target = _agent_name(session, c.target_agent_id)
        lines.append(f"### {source} → {target} ({c.category.value}, {c.priority} priority)")
        lines.append(f"")
        if c.risks:
            lines.append(f"**Risks:**")
            for r in c.risks:
                lines.append(f"- {r}")
            lines.append(f"")
        if c.missing_considerations:
            lines.append(f"**Missing Considerations:**")
            for m in c.missing_considerations:
                lines.append(f"- {m}")
            lines.append(f"")
        if c.alternative_proposal:
            lines.append(f"**Alternative:** {c.alternative_proposal}")
            lines.append(f"")
        lines.append(f"---")
        lines.append(f"")


def _add_resolved_risks(lines: list[str], session: Session) -> None:
    resolved = [q for q in session.pending_questions if q.resolved]
    if not resolved:
        return
    lines.append(f"## Resolved Questions")
    lines.append(f"")
    for q in resolved:
        lines.append(f"- **Q**: {q.question}")
        lines.append(f"  **A**: {q.resolution}")
    lines.append(f"")


def _add_key_improvements(lines: list[str], session: Session) -> None:
    if not session.revisions and not session.optimizations:
        return
    lines.append(f"## Key Improvements")
    lines.append(f"")
    for r in session.revisions:
        agent = _agent_name(session, r.agent_id)
        lines.append(f"### Revision by {agent}")
        lines.append(f"")
        if r.accepted_feedback:
            lines.append(f"**Accepted:**")
            for f in r.accepted_feedback:
                lines.append(f"- {f}")
            lines.append(f"")
        lines.append(f"**Design Change:** {r.changed_design[:300]}")
        lines.append(f"")

    for o in session.optimizations:
        agent = _agent_name(session, o.agent_id)
        lines.append(f"- **{agent}**: {o.description} (Impact: {o.impact or 'N/A'}, Tradeoff: {o.tradeoff or 'N/A'})")
    lines.append(f"")


def _add_event_timeline(lines: list[str], session: Session) -> None:
    if not session.events:
        return
    lines.append(f"## Event Timeline")
    lines.append(f"")
    lines.append(f"| Time | Phase | Agent | Event |")
    lines.append(f"|------|-------|-------|-------|")
    for e in session.events[-30:]:
        agent = _agent_name(session, e.source_agent) if e.source_agent != "system" else "System"
        lines.append(f"| {e.created_at[:19]} | {e.phase.value} | {agent} | {e.content[:80]} |")
    lines.append(f"")


def _extract_decisions(session: Session) -> list[dict]:
    decisions = []

    for group in session.merged_assumptions:
        for a in group.assumptions:
            if a.human_choice:
                decisions.append({
                    "title": f"Assumption: {a.assumption[:60]}",
                    "decision": a.human_choice,
                    "alternatives": [alt.label for alt in a.alternatives if alt.label != a.human_choice],
                    "tradeoffs": a.rationale or "Not specified",
                    "rationale": f"Resolved during clarification phase (dimension: {group.dimension})",
                })

    proposals = _get_latest_proposals(session)
    for p in proposals:
        decisions.append({
            "title": f"Architecture by {_agent_name(session, p.agent_id)}",
            "decision": p.architecture or p.raw_content or "No architecture specified",
            "alternatives": [c.alternative_proposal for c in session.challenges if c.alternative_proposal],
            "tradeoffs": p.tradeoffs or "Not specified",
            "rationale": f"Based on proposal with assumptions: {p.assumptions or 'N/A'}",
        })

    for o in _get_latest_optimizations(session):
        decisions.append({
            "title": f"Optimization by {_agent_name(session, o.agent_id)}",
            "decision": o.description,
            "alternatives": [],
            "tradeoffs": o.tradeoff or "Not specified",
            "rationale": f"Impact: {o.impact or 'N/A'}, Complexity change: {o.complexity_change or 'N/A'}",
        })

    return decisions


def _get_latest_proposals(session: Session) -> list[Proposal]:
    if not session.proposals:
        return []
    latest_round = max(p.round_number for p in session.proposals)
    result = [p for p in session.proposals if p.round_number == latest_round]
    return result if result else session.proposals[-len(session.agents):]


def _get_latest_revisions(session: Session) -> list[Revision]:
    if not session.revisions:
        return []
    latest_round = max(r.round_number for r in session.revisions)
    return [r for r in session.revisions if r.round_number == latest_round]


def _get_latest_optimizations(session: Session) -> list[Optimization]:
    if not session.optimizations:
        return []
    latest_round = max(o.round_number for o in session.optimizations)
    return [o for o in session.optimizations if o.round_number == latest_round]


def _agent_name(session: Session, agent_id: str) -> str:
    for a in session.agents:
        if a.agent_id == agent_id:
            return a.name
    return agent_id


def _get_agent_perspective(session: Session, agent_id: str, round_number: int) -> str:
    for p in session.proposals:
        if p.agent_id == agent_id and p.round_number == round_number and p.perspective:
            return p.perspective
    return ""
