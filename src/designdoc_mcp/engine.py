from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from .clarity_config import (
    DIMENSION_KEYWORDS,
    FIELD_COMPLETION_BONUS,
    LENGTH_NORMALIZATION_FACTOR,
    MAX_CLARITY_SCORE,
    MAX_LENGTH_BONUS,
    validate_config,
)
from .constants import (
    ACTION_AUTO_SKIP_CLARIFICATION,
    ACTION_DELTA_APPENDED_TO_DEBATE,
    ACTION_DELTA_CLEAR_NO_CLARIFICATION_NEEDED,
    ACTION_DELTA_NEEDS_CLARIFICATION,
    ACTION_NEEDS_CLARIFICATION,
    ACTION_REJOINED,
    ACTION_REGISTERED,
    ASSUMPTION_SIMILARITY_THRESHOLD,
    CONSENSUS_PARTIAL_AGREEMENT_MIN,
    CONSENSUS_SEVERE_DISAGREEMENT_THRESHOLD,
    DEFAULT_CHALLENGE_CATEGORY,
    DEFAULT_CHALLENGE_PRIORITY,
    DEFAULT_CONFIDENCE,
    DEFAULT_MAX_ROUNDS,
    DEFAULT_MIN_ROUNDS,
    DEFAULT_VOTE_TYPE,
    NOVELTY_THRESHOLD,
    TASK_POLL_TIMEOUT,
)
from .events import event_bus

logger = logging.getLogger(__name__)

from .models import (
    ASSUMPTION_DIMENSIONS,
    CLARIFY_PHASES,
    CLARITY_DIMENSIONS,
    CLARITY_THRESHOLD,
    AgentInfo,
    Assumption,
    AssumptionAlternative,
    Challenge,
    ChallengeCategory,
    ChallengePriority,
    ConsensusVote,
    DebatePhase,
    DecisionOption,
    DecisionPoint,
    DevilsAdvocate,
    Event,
    EventType,
    HumanVote,
    MergedAssumptionGroup,
    MAX_CLARIFY_ROUNDS,
    Optimization,
    PERSPECTIVE_DESCRIPTIONS,
    PERSPECTIVES,
    PHASE_DESCRIPTIONS,
    PHASE_ORDER,
    PendingQuestion,
    Proposal,
    QuestionOption,
    RefinedRequirement,
    Requirement,
    RequirementDelta,
    Revision,
    Session,
    SessionStatus,
    VoteType,
    AGENT_INACTIVE_TIMEOUT_SECONDS,
)
from .store import SessionStore


class CollaborationEngine:
    def __init__(self, store: SessionStore):
        self.store = store
        validate_config()

    def create_session(
        self,
        title: str,
        description: str,
        min_rounds: int = DEFAULT_MIN_ROUNDS,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
    ) -> Session:
        session = Session(
            session_id=uuid.uuid4().hex[:12],
            title=title,
            description=description,
            min_rounds=min_rounds,
            max_rounds=max_rounds,
        )
        return self.store.create_session(session)

    def submit_requirement(
        self,
        session_id: str,
        problem_statement: str,
        constraints: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
        open_questions: list[str] | None = None,
        tech_preferences: list[str] | None = None,
        forbidden_items: list[str] | None = None,
    ) -> Requirement:
        session = self._get(session_id)
        req = Requirement(
            requirement_id=uuid.uuid4().hex[:8],
            session_id=session_id,
            problem_statement=problem_statement,
            constraints=constraints or [],
            acceptance_criteria=acceptance_criteria or [],
            open_questions=open_questions or [],
            tech_preferences=tech_preferences or [],
            forbidden_items=forbidden_items or [],
            original_statement=problem_statement,
        )
        self._evaluate_clarity(req)
        session.requirement = req
        self._add_event(session, EventType.SYSTEM_EVENT, "system", content="Requirement submitted")
        clarity_msg = f"Clarity score: {req.clarity_score:.2f} ({'skip' if req.skip_clarification else 'needs'} clarification)"
        self._add_event(session, EventType.SYSTEM_EVENT, "system", content=clarity_msg)
        self.store.save_requirement_file(session_id, problem_statement)
        self.store.update_session(session)
        return req

    def register_agent(
        self,
        session_id: str = "",
        name: str = "",
        model: str = "",
        provider: str = "",
        agent_identity: str = "",
        client_type: str = "",
    ) -> AgentInfo | dict:
        if not name:
            name = f"Agent-{uuid.uuid4().hex[:6]}"
        if not session_id:
            active = [s for s in self.store.list_sessions() if s.status not in (SessionStatus.ARCHIVED, SessionStatus.COMPLETED)]
            if len(active) == 0:
                logger.warning("register_agent: no active sessions found")
                return {"action": "error", "message": "No active sessions. Create one via the Web UI at http://localhost:8765"}
            if len(active) == 1:
                session_id = active[0].session_id
                logger.info("register_agent: auto-detected single session %s", session_id)
            else:
                logger.info("register_agent: %d active sessions, returning list", len(active))
                sessions_info = []
                for s in active:
                    agents_str = ", ".join(a.name for a in s.agents) if s.agents else "none"
                    sessions_info.append({
                        "session_id": s.session_id,
                        "title": s.title,
                        "phase": s.current_phase.value,
                        "agents_count": len(s.agents),
                    })
                return {"action": "choose_session", "message": "Multiple active sessions found. Choose one.", "sessions": sessions_info}
        session = self._get(session_id)

        # --- Auto rejoin via stable identity ---
        rejoined = False
        if agent_identity:
            for a in session.agents:
                if a.agent_identity == agent_identity:
                    # Rejoin: restore existing agent, update metadata
                    a.name = name
                    a.model = model or a.model
                    a.provider = provider or a.provider
                    a.client_type = client_type or a.client_type
                    a.is_active = True
                    a.last_active_at = datetime.now(timezone.utc).isoformat()
                    a.runtime_mode = "persistent_worker"
                    agent = a
                    rejoined = True
                    logger.info("register_agent: auto-rejoin via identity %s → agent %s", agent_identity, a.agent_id)
                    break

        if not rejoined:
            # New registration: check phase restrictions
            late_registration_phases = {
                DebatePhase.CRITIC,
                DebatePhase.REVISION,
                DebatePhase.OPTIMIZATION,
                DebatePhase.DEVILS_ADVOCATE,
                DebatePhase.CONSENSUS,
            }
            if session.current_phase in late_registration_phases:
                raise ValueError(
                    f"Cannot register new agents during {session.current_phase.value} phase. "
                    f"Register before Proposal phase or after human review."
                )
            if session.status in (SessionStatus.COMPLETED, SessionStatus.ARCHIVED):
                raise ValueError(f"Cannot register agents in {session.status.value} session")

            # Generate agent_id from name (+ model if provided)
            base_id = name.lower().replace(" ", "_")
            if model:
                model_slug = model.lower().replace("-", "_").replace(".", "_").replace(" ", "_")
                agent_id = f"{base_id}__{model_slug}"
            else:
                agent_id = base_id

            # Detect persistent capability
            runtime_mode = "persistent_worker"
            if client_type in ("cursor", "claude_code", "atomcode"):
                runtime_mode = "persistent_worker"

            agent = AgentInfo(
                agent_id=agent_id,
                name=name,
                model=model,
                provider=provider,
                agent_identity=agent_identity or agent_id,
                client_type=client_type,
                runtime_mode=runtime_mode,
            )

            # Check if agent_id already exists (legacy rejoin by agent_id)
            existing_ids = {a.agent_id for a in session.agents}
            if agent_id in existing_ids:
                old_perspective = ""
                for a in session.agents:
                    if a.agent_id == agent_id:
                        old_perspective = a.current_perspective
                        break
                agent.current_perspective = old_perspective
                session.agents = [a if a.agent_id != agent_id else agent for a in session.agents]
                rejoined = True
                logger.info("register_agent: re-registering existing agent %s in session %s", agent_id, session_id)
            else:
                session.agents.append(agent)
                logger.info("register_agent: new agent %s added to session %s (total: %d)", agent_id, session_id, len(session.agents))

        # Tag the agent with rejoin status for the caller
        agent._rejoined = rejoined

        model_info = f" (model={model}, provider={provider})" if model else ""
        action_word = ACTION_REJOINED if rejoined else ACTION_REGISTERED
        self._add_event(session, EventType.SYSTEM_EVENT, agent.agent_id, content=f"Agent {name}{model_info} {action_word}")
        self.store.update_session(session)
        logger.info("register_agent: session updated and persisted, agents in session: %s", [a.agent_id for a in session.agents])
        return agent

    def deregister_agent(self, session_id: str, agent_id: str) -> dict:
        """Deregister an agent from a session. The agent becomes inactive."""
        session = self._get(session_id)
        agent = None
        for a in session.agents:
            if a.agent_id == agent_id:
                agent = a
                break
        if agent is None:
            raise ValueError(f"Agent '{agent_id}' not found in session '{session_id}'")
        agent.is_active = False
        agent.last_active_at = datetime.now(timezone.utc).isoformat()
        self._add_event(session, EventType.SYSTEM_EVENT, agent_id, content=f"Agent {agent.name} deregistered")
        self.store.update_session(session)
        logger.info("deregister_agent: agent %s deregistered from session %s", agent_id, session_id)
        # Check if phase completion is affected
        self._check_phase_completion(session, force_active_only=True)
        return {"action": "deregistered", "agent_id": agent_id, "session_id": session_id}

    def delete_session(self, session_id: str) -> dict:
        """Delete a session. Only ARCHIVED sessions can be deleted."""
        session = self._get(session_id)
        if session.status != SessionStatus.ARCHIVED:
            raise ValueError(f"Only archived sessions can be deleted. Current status: {session.status.value}")
        self.store.delete_session(session_id)
        logger.info("delete_session: session %s deleted", session_id)
        return {"action": "deleted", "session_id": session_id}

    def start_clarification(self, session_id: str) -> dict:
        session = self._get(session_id)
        if len(session.agents) < 1:
            raise ValueError("At least 1 agent required")
        if session.requirement is None:
            raise ValueError("Requirement must be submitted first")

        if session.requirement.skip_clarification:
            return self._skip_clarification(session_id)

        session.status = SessionStatus.CLARIFY_IDENTIFY
        session.current_phase = DebatePhase.CLARIFY_IDENTIFY
        session.clarify_round = 1
        self._add_event(session, EventType.SYSTEM_EVENT, "system", content="Clarification phase started - identify assumptions")
        self.store.update_session(session)
        return {
            "session_id": session_id,
            "phase": DebatePhase.CLARIFY_IDENTIFY.value,
            "clarify_round": 1,
            "instruction": PHASE_DESCRIPTIONS[DebatePhase.CLARIFY_IDENTIFY],
            "dimensions": ASSUMPTION_DIMENSIONS,
            "agents": [a.agent_id for a in session.agents],
        }

    def _evaluate_clarity(self, req: Requirement) -> None:
        text = (req.problem_statement or "").lower()
        all_text = " ".join([
            text,
            " ".join(req.constraints).lower(),
            " ".join(req.acceptance_criteria).lower(),
            " ".join(req.tech_preferences).lower(),
            " ".join(req.forbidden_items).lower(),
        ])

        dimensions_covered: dict[str, bool] = {}
        for dim, keywords in DIMENSION_KEYWORDS.items():
            dimensions_covered[dim] = any(kw in all_text for kw in keywords)

        covered_count = sum(1 for v in dimensions_covered.values() if v)
        total = len(dimensions_covered)

        text_length = len(req.problem_statement)
        length_bonus = min(MAX_LENGTH_BONUS, text_length / LENGTH_NORMALIZATION_FACTOR)

        has_constraints = len(req.constraints) > 0
        has_criteria = len(req.acceptance_criteria) > 0
        has_forbidden = len(req.forbidden_items) > 0
        field_bonus = FIELD_COMPLETION_BONUS * sum([has_constraints, has_criteria, has_forbidden])

        base_score = covered_count / total
        req.clarity_score = min(MAX_CLARITY_SCORE, base_score + length_bonus + field_bonus)
        req.clarity_dimensions = dimensions_covered
        req.skip_clarification = req.clarity_score >= CLARITY_THRESHOLD

    def _skip_clarification(self, session_id: str) -> dict:
        session = self._get(session_id)
        session.current_phase = DebatePhase.PROPOSAL
        session.status = SessionStatus.PROPOSAL
        session.current_round = 1
        self._assign_perspectives(session)
        self._add_event(
            session, EventType.SYSTEM_EVENT, "system",
            content=f"Clarification skipped (clarity_score={session.requirement.clarity_score:.2f} >= {CLARITY_THRESHOLD}). Direct to PROPOSAL.",
        )
        self.store.update_session(session)
        return {
            "session_id": session_id,
            "phase": DebatePhase.PROPOSAL.value,
            "action": "clarification_skipped",
            "reason": f"Requirement clarity score {session.requirement.clarity_score:.2f} exceeds threshold {CLARITY_THRESHOLD}",
            "clarity_dimensions": session.requirement.clarity_dimensions,
            "instruction": PHASE_DESCRIPTIONS[DebatePhase.PROPOSAL],
            "perspectives": {a.agent_id: a.current_perspective for a in session.agents if a.current_perspective},
            "agents": [a.agent_id for a in session.agents],
        }

    def force_skip_clarification(self, session_id: str) -> dict:
        session = self._get(session_id)
        if session.requirement is None:
            raise ValueError("Requirement must be submitted first")
        if session.current_phase not in (
            DebatePhase.CLARIFY_IDENTIFY,
            DebatePhase.CLARIFY_REFINE,
            DebatePhase.CLARIFY_REVIEW,
            DebatePhase.CLARIFY_REWRITE,
        ):
            raise ValueError(f"Cannot skip clarification from phase {session.current_phase.value}")
        session.requirement.skip_clarification = True
        return self._skip_clarification(session_id)

    def add_requirement_delta(
        self,
        session_id: str,
        delta_statement: str,
        constraints: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
        parent_delta_id: str | None = None,
    ) -> dict[str, Any]:
        session = self._get(session_id)
        if session.requirement is None:
            raise ValueError("Base requirement must be submitted first")

        if parent_delta_id is not None:
            parent_exists = any(d.delta_id == parent_delta_id for d in session.requirement_deltas)
            if not parent_exists:
                raise ValueError(f"Parent delta '{parent_delta_id}' not found in session")

        delta_req = Requirement(
            requirement_id=uuid.uuid4().hex[:8],
            session_id=session_id,
            problem_statement=delta_statement,
            constraints=constraints or [],
            acceptance_criteria=acceptance_criteria or [],
            original_statement=delta_statement,
        )
        self._evaluate_clarity(delta_req)

        delta = RequirementDelta(
            delta_id=uuid.uuid4().hex[:8],
            session_id=session_id,
            parent_delta_id=parent_delta_id,
            problem_statement=delta_statement,
            constraints=constraints or [],
            acceptance_criteria=acceptance_criteria or [],
            clarity_score=delta_req.clarity_score,
            clarity_dimensions=delta_req.clarity_dimensions,
            skip_clarification=delta_req.skip_clarification,
        )
        session.requirement_deltas.append(delta)

        combined_statement = session.requirement.problem_statement
        if delta_statement:
            combined_statement += f"\n\n--- Supplementary Requirement ---\n{delta_statement}"

        combined_constraints = list(session.requirement.constraints) + (constraints or [])
        combined_criteria = list(session.requirement.acceptance_criteria) + (acceptance_criteria or [])

        session.requirement.problem_statement = combined_statement
        session.requirement.constraints = combined_constraints
        session.requirement.acceptance_criteria = combined_criteria

        self._evaluate_clarity(session.requirement)

        self._add_event(
            session, EventType.SYSTEM_EVENT, "system",
            content=f"Requirement delta added: {delta_statement[:100]}",
        )
        self._add_event(
            session, EventType.SYSTEM_EVENT, "system",
            content=f"Updated clarity score: {session.requirement.clarity_score:.2f} (delta alone: {delta_req.clarity_score:.2f})",
        )

        self.store.save_requirement_file(session_id, combined_statement)
        self.store.update_session(session)

        result: dict[str, Any] = {
            "session_id": session_id,
            "delta_id": delta.delta_id,
            "delta_clarity_score": delta_req.clarity_score,
            "delta_clarity_dimensions": delta_req.clarity_dimensions,
            "delta_skip_clarification": delta_req.skip_clarification,
            "combined_clarity_score": session.requirement.clarity_score,
            "combined_clarity_dimensions": session.requirement.clarity_dimensions,
            "combined_skip_clarification": session.requirement.skip_clarification,
        }

        if session.current_phase in (
            DebatePhase.PROPOSAL,
            DebatePhase.CRITIC,
            DebatePhase.REVISION,
            DebatePhase.OPTIMIZATION,
            DebatePhase.DEVILS_ADVOCATE,
            DebatePhase.CONSENSUS,
        ):
            result["action"] = ACTION_DELTA_APPENDED_TO_DEBATE
            result["current_phase"] = session.current_phase.value
            result["message"] = "Delta appended to existing debate. Agents should consider the new requirement in ongoing discussion."
        elif session.current_phase in (
            DebatePhase.CLARIFY_IDENTIFY,
            DebatePhase.CLARIFY_REFINE,
            DebatePhase.CLARIFY_REVIEW,
            DebatePhase.CLARIFY_REWRITE,
        ):
            if delta_req.skip_clarification:
                result["action"] = ACTION_DELTA_CLEAR_NO_CLARIFICATION_NEEDED
                result["message"] = "Delta is clear enough. Continue current clarification for the base requirement."
            else:
                result["action"] = ACTION_DELTA_NEEDS_CLARIFICATION
                result["message"] = "Delta is fuzzy. Agents should also submit assumptions about the delta during current clarification."
                result["delta_dimensions_to_clarify"] = [
                    dim for dim, covered in delta_req.clarity_dimensions.items() if not covered
                ]
        else:
            if session.requirement.skip_clarification:
                result["action"] = ACTION_AUTO_SKIP_CLARIFICATION
                result["message"] = "Combined requirement is clear enough. Can start clarification to skip directly to PROPOSAL."
            else:
                result["action"] = ACTION_NEEDS_CLARIFICATION
                result["message"] = "Combined requirement needs clarification. Start clarification to refine."
                result["dimensions_to_clarify"] = [
                    dim for dim, covered in session.requirement.clarity_dimensions.items() if not covered
                ]

        return result

    def submit_assumptions(
        self,
        session_id: str,
        agent_id: str,
        assumptions: list[dict],
    ) -> list[Assumption]:
        session = self._get(session_id)
        self._validate_phase(session, DebatePhase.CLARIFY_IDENTIFY)
        self._validate_agent(session, agent_id)
        self._touch_agent(session, agent_id)

        existing = [a for a in session.assumptions if a.agent_id == agent_id and a.clarify_round == session.clarify_round]
        if existing:
            raise ValueError(f"Agent '{agent_id}' already submitted assumptions for clarify round {session.clarify_round}")

        created = []
        for a in assumptions:
            alt_models = [
                AssumptionAlternative(label=alt.get("label", ""), description=alt.get("description", ""))
                for alt in a.get("alternatives", [])
            ]
            if not any(alt.label.lower() == "other" for alt in alt_models):
                alt_models.append(AssumptionAlternative(label="Other", description="Custom input"))

            assumption = Assumption(
                assumption_id=uuid.uuid4().hex[:8],
                session_id=session_id,
                agent_id=agent_id,
                dimension=a.get("dimension", "core_entities"),
                assumption=a.get("assumption", ""),
                confidence=a.get("confidence", 0.5),
                alternatives=alt_models,
                rationale=a.get("rationale", ""),
                clarify_round=session.clarify_round,
            )
            session.assumptions.append(assumption)
            created.append(assumption)

        self._add_event(session, EventType.ASSUMPTION, agent_id, content=f"Submitted {len(created)} assumptions")
        self.store.update_session(session)
        self._check_phase_completion(session)
        return created

    def supplement_assumption_options(
        self,
        session_id: str,
        agent_id: str,
        supplements: list[dict],
    ) -> None:
        session = self._get(session_id)
        self._validate_phase(session, DebatePhase.CLARIFY_REFINE)
        self._validate_agent(session, agent_id)
        self._touch_agent(session, agent_id)

        for sup in supplements:
            target_id = sup.get("assumption_id", "")
            for a in session.assumptions:
                if a.assumption_id == target_id:
                    new_alt = AssumptionAlternative(
                        label=sup.get("label", ""),
                        description=sup.get("description", ""),
                    )
                    a.alternatives.append(new_alt)
                    break

        if agent_id not in session.clarify_refine_submitted:
            session.clarify_refine_submitted.append(agent_id)

        self._add_event(session, EventType.ASSUMPTION_SUPPLEMENT, agent_id, content=f"Supplemented {len(supplements)} assumption options")
        self.store.update_session(session)
        self._check_phase_completion(session)

    def get_merged_assumptions(self, session_id: str) -> list[MergedAssumptionGroup]:
        session = self._get(session_id)
        if not session.merged_assumptions:
            self._merge_assumptions(session)
        return session.merged_assumptions

    def _merge_assumptions(self, session: Session) -> None:
        by_dimension: dict[str, list[Assumption]] = {}
        for a in session.assumptions:
            by_dimension.setdefault(a.dimension, []).append(a)

        merged = []
        for dim in ASSUMPTION_DIMENSIONS:
            dim_assumptions = by_dimension.get(dim, [])
            if not dim_assumptions:
                continue

            grouped: dict[str, list[Assumption]] = {}
            for a in dim_assumptions:
                key = a.assumption.lower().strip()[:60]
                matched = False
                for existing_key in list(grouped.keys()):
                    if self._assumptions_similar(key, existing_key):
                        grouped[existing_key].append(a)
                        matched = True
                        break
                if not matched:
                    grouped[key] = [a]

            for key, group in grouped.items():
                primary = group[0]
                all_alts: list[AssumptionAlternative] = list(primary.alternatives)
                seen_labels = {alt.label.lower() for alt in all_alts}
                for other in group[1:]:
                    for alt in other.alternatives:
                        if alt.label.lower() not in seen_labels:
                            all_alts.append(alt)
                            seen_labels.add(alt.label.lower())

                if not any(alt.label.lower() == "other" for alt in all_alts):
                    all_alts.append(AssumptionAlternative(label="Other", description="Custom input"))

                divergent = len(group) > 1 and len(set(a.assumption for a in group)) > 1

                merged.append(MergedAssumptionGroup(
                    dimension=dim,
                    assumptions=[Assumption(
                        assumption_id=primary.assumption_id,
                        session_id=primary.session_id,
                        agent_id="merged",
                        dimension=primary.dimension,
                        assumption=primary.assumption,
                        confidence=max(a.confidence for a in group),
                        alternatives=all_alts,
                        rationale=primary.rationale,
                        human_choice=primary.human_choice,
                    )],
                    divergent=divergent,
                ))

        session.merged_assumptions = merged
        self.store.update_session(session)

    def _assumptions_similar(self, a: str, b: str) -> bool:
        a_words = set(a.split())
        b_words = set(b.split())
        if not a_words or not b_words:
            return False
        overlap = len(a_words & b_words) / max(len(a_words), len(b_words))
        return overlap > ASSUMPTION_SIMILARITY_THRESHOLD

    def review_assumptions(
        self,
        session_id: str,
        choices: list[dict],
    ) -> None:
        session = self._get(session_id)

        for choice in choices:
            assumption_id = choice.get("assumption_id", "")
            human_choice = choice.get("choice", "")
            for group in session.merged_assumptions:
                for a in group.assumptions:
                    if a.assumption_id == assumption_id:
                        a.human_choice = human_choice
                        break

        all_reviewed = all(
            all(a.human_choice for a in group.assumptions)
            for group in session.merged_assumptions
            if group.divergent
        )

        if all_reviewed:
            session.current_phase = DebatePhase.CLARIFY_REWRITE
            session.status = SessionStatus.CLARIFY_REWRITE
            self._add_event(session, EventType.HUMAN_DECISION, "human", content="Assumptions reviewed, moving to rewrite phase")
        else:
            self._add_event(session, EventType.HUMAN_DECISION, "human", content="Partial assumption review")

        self.store.update_session(session)

    def submit_refined_requirement(
        self,
        session_id: str,
        agent_id: str,
        refined_statement: str,
        constraints: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
    ) -> RefinedRequirement:
        session = self._get(session_id)
        self._validate_phase(session, DebatePhase.CLARIFY_REWRITE)
        self._validate_agent(session, agent_id)
        self._touch_agent(session, agent_id)

        refined = RefinedRequirement(
            refine_id=uuid.uuid4().hex[:8],
            session_id=session_id,
            agent_id=agent_id,
            refined_statement=refined_statement,
            constraints=constraints or [],
            acceptance_criteria=acceptance_criteria or [],
        )
        session.refined_requirements.append(refined)
        self._add_event(session, EventType.REQUIREMENT_REFINE, agent_id, content=f"Proposed refined requirement")
        self.store.update_session(session)
        self._check_phase_completion(session)
        return refined

    def approve_refined_requirement(
        self,
        session_id: str,
        refine_id: str,
    ) -> Requirement:
        session = self._get(session_id)

        refined = None
        for r in session.refined_requirements:
            if r.refine_id == refine_id:
                refined = r
                break
        if refined is None:
            raise ValueError(f"Refined requirement '{refine_id}' not found")

        if session.requirement:
            session.requirement.problem_statement = refined.refined_statement
            session.requirement.constraints = refined.constraints
            session.requirement.acceptance_criteria = refined.acceptance_criteria
            session.requirement.is_refined = True
        else:
            session.requirement = Requirement(
                requirement_id=uuid.uuid4().hex[:8],
                session_id=session_id,
                problem_statement=refined.refined_statement,
                constraints=refined.constraints,
                acceptance_criteria=refined.acceptance_criteria,
                is_refined=True,
                original_statement=session.description,
            )

        self.store.save_requirement_file(session_id, refined.refined_statement)
        self._add_event(session, EventType.HUMAN_DECISION, "human", content="Refined requirement approved")

        session.current_phase = DebatePhase.PROPOSAL
        session.status = SessionStatus.PROPOSAL
        session.current_round = 1
        self._assign_perspectives(session)
        self._add_event(session, EventType.SYSTEM_EVENT, "system", content="Debate started - Phase: PROPOSAL")

        self.store.update_session(session)
        return session.requirement

    def start_debate(self, session_id: str) -> dict:
        session = self._get(session_id)
        if len(session.agents) < 2:
            raise ValueError("At least 2 agents required to start debate")
        if session.requirement is None:
            raise ValueError("Requirement must be submitted before starting debate")

        self._assign_perspectives(session)

        session.status = SessionStatus.PROPOSAL
        session.current_phase = DebatePhase.PROPOSAL
        session.current_round = 1
        self._add_event(session, EventType.SYSTEM_EVENT, "system", content="Debate started - Phase: PROPOSAL")
        self.store.update_session(session)
        return {
            "session_id": session_id,
            "phase": DebatePhase.PROPOSAL.value,
            "round": 1,
            "instruction": PHASE_DESCRIPTIONS[DebatePhase.PROPOSAL],
            "perspectives": {a.agent_id: a.current_perspective for a in session.agents},
            "agents": [a.agent_id for a in session.agents],
        }

    def _assign_perspectives(self, session: Session) -> None:
        available = list(PERSPECTIVES)
        random.shuffle(available)
        for i, agent in enumerate(session.agents):
            agent.current_perspective = available[i % len(available)]

    def submit_proposal(
        self,
        session_id: str,
        agent_id: str,
        architecture: str,
        tech_stack: str = "",
        tradeoffs: str = "",
        risks: str = "",
        assumptions: str = "",
        unknowns: str = "",
        raw_content: str = "",
    ) -> Proposal:
        session = self._get(session_id)
        self._validate_phase(session, DebatePhase.PROPOSAL)
        self._validate_agent(session, agent_id)
        self._touch_agent(session, agent_id)

        existing = [p for p in session.proposals if p.agent_id == agent_id and p.round_number == session.current_round]
        if existing:
            raise ValueError(f"Agent '{agent_id}' already submitted a proposal for round {session.current_round}")

        agent = next(a for a in session.agents if a.agent_id == agent_id)
        proposal = Proposal(
            proposal_id=uuid.uuid4().hex[:8],
            session_id=session_id,
            agent_id=agent_id,
            round_number=session.current_round,
            perspective=agent.current_perspective,
            architecture=architecture,
            tech_stack=tech_stack,
            tradeoffs=tradeoffs,
            risks=risks,
            assumptions=assumptions,
            unknowns=unknowns,
            raw_content=raw_content,
        )
        session.proposals.append(proposal)
        self._add_event(session, EventType.PROPOSAL, agent_id, content=f"Submitted proposal (perspective: {agent.current_perspective}): {architecture[:100]}...")
        self.store.update_session(session)
        self._check_phase_completion(session)
        return proposal

    def submit_challenge(
        self,
        session_id: str,
        agent_id: str,
        target_agent_id: str,
        target_proposal_id: str,
        risks: list[str],
        missing_considerations: list[str],
        alternative_proposal: str = "",
        category: str = DEFAULT_CHALLENGE_CATEGORY,
        priority: str = DEFAULT_CHALLENGE_PRIORITY,
        confidence: float = DEFAULT_CONFIDENCE,
    ) -> Challenge:
        session = self._get(session_id)
        self._validate_phase(session, DebatePhase.CRITIC)
        self._validate_agent(session, agent_id)
        self._touch_agent(session, agent_id)

        # 验证目标 agent 存在
        active_count = self._active_agent_count(session)
        if target_agent_id == agent_id and active_count > 1:
            raise ValueError("Cannot challenge your own proposal (single-agent mode allows self-review)")
        self._validate_agent(session, target_agent_id)

        # 验证目标 proposal 存在
        target_proposal_ids = {p.proposal_id for p in session.proposals if p.round_number == session.current_round}
        if target_proposal_id not in target_proposal_ids:
            raise ValueError(f"Proposal '{target_proposal_id}' not found in current round")

        challenge = Challenge(
            challenge_id=uuid.uuid4().hex[:8],
            session_id=session_id,
            agent_id=agent_id,
            target_agent_id=target_agent_id,
            target_proposal_id=target_proposal_id,
            round_number=session.current_round,
            risks=risks,
            missing_considerations=missing_considerations,
            alternative_proposal=alternative_proposal,
            category=ChallengeCategory(category),
            priority=ChallengePriority(priority),
            confidence=confidence,
        )
        session.challenges.append(challenge)
        self._add_event(
            session,
            EventType.CHALLENGE,
            agent_id,
            target_agent_id,
            f"Challenged with {len(risks)} risks, {len(missing_considerations)} missing considerations",
        )
        self.store.update_session(session)
        self._check_phase_completion(session)
        return challenge

    def submit_revision(
        self,
        session_id: str,
        agent_id: str,
        accepted_feedback: list[str],
        rejected_feedback: list[str],
        rejection_reasons: list[str],
        changed_design: str,
    ) -> Revision:
        session = self._get(session_id)
        self._validate_phase(session, DebatePhase.REVISION)
        self._validate_agent(session, agent_id)
        self._touch_agent(session, agent_id)

        revision = Revision(
            revision_id=uuid.uuid4().hex[:8],
            session_id=session_id,
            agent_id=agent_id,
            round_number=session.current_round,
            accepted_feedback=accepted_feedback,
            rejected_feedback=rejected_feedback,
            rejection_reasons=rejection_reasons,
            changed_design=changed_design,
        )
        session.revisions.append(revision)
        self._add_event(session, EventType.REVISION, agent_id, content=f"Revised: accepted {len(accepted_feedback)}, rejected {len(rejected_feedback)}")
        self.store.update_session(session)
        self._check_phase_completion(session)
        return revision

    def submit_decision_points(
        self,
        session_id: str,
        agent_id: str,
        decision_points: list[dict],
    ) -> dict:
        """Submit decision points identified during Critic phase.
        Called alongside submit_challenge to extract key decision divergences.

        Args:
            decision_points: List of dicts with keys: topic, description, options, constraints
                Each option: {label, reasoning, pros, cons}
        """
        session = self._get(session_id)
        self._validate_phase(session, DebatePhase.CRITIC)
        self._validate_agent(session, agent_id)
        self._touch_agent(session, agent_id)

        added = []
        for dp_data in decision_points:
            topic = dp_data.get("topic", "").strip()
            if not topic:
                continue
            options = []
            for opt_data in dp_data.get("options", []):
                options.append(DecisionOption(
                    option_id=f"{agent_id}_{topic}_{opt_data.get('label', 'unknown')}".lower().replace(" ", "_"),
                    label=opt_data.get("label", ""),
                    proposed_by=agent_id,
                    reasoning=opt_data.get("reasoning", ""),
                    pros=opt_data.get("pros", []),
                    cons=opt_data.get("cons", []),
                ))
            dp = DecisionPoint(
                decision_id=f"dp_{uuid.uuid4().hex[:8]}",
                topic=topic,
                description=dp_data.get("description", ""),
                options=options,
                constraints=dp_data.get("constraints", []),
            )
            session.decision_points.append(dp)
            added.append(dp.decision_id)

        self._add_event(session, EventType.SYSTEM_EVENT, agent_id, content=f"Submitted {len(added)} decision points")
        self.store.update_session(session)
        logger.info("submit_decision_points: agent %s submitted %d points in session %s", agent_id, len(added), session_id)
        return {"action": "submitted", "count": len(added), "decision_ids": added}

    def _merge_decision_points(self, session: Session) -> None:
        """Merge decision points by topic. Same-topic points get their options combined."""
        by_topic: dict[str, list[DecisionPoint]] = {}
        for dp in session.decision_points:
            key = dp.topic.lower().strip()
            if key not in by_topic:
                by_topic[key] = []
            by_topic[key].append(dp)

        merged = []
        for topic, dps in by_topic.items():
            if len(dps) == 1:
                merged.append(dps[0])
                continue
            # Merge options from all DPs with the same topic
            all_options = []
            seen_labels: dict[str, DecisionOption] = {}
            for dp in dps:
                for opt in dp.options:
                    label_key = opt.label.lower().strip()
                    if label_key in seen_labels:
                        # Merge: combine reasoning from multiple agents
                        existing = seen_labels[label_key]
                        if opt.reasoning and opt.reasoning not in existing.reasoning:
                            existing.reasoning += f" | {opt.proposed_by}: {opt.reasoning}"
                        existing.pros = list(set(existing.pros + opt.pros))
                        existing.cons = list(set(existing.cons + opt.cons))
                    else:
                        seen_labels[label_key] = opt.model_copy()
                        all_options.append(seen_labels[label_key])

            all_constraints = list(set(c for dp in dps for c in dp.constraints))
            best_desc = max(dps, key=lambda d: len(d.description)).description

            merged.append(DecisionPoint(
                decision_id=dps[0].decision_id,
                topic=dps[0].topic,
                description=best_desc,
                options=all_options,
                constraints=all_constraints,
                human_choice=dps[0].human_choice,
                human_custom=dps[0].human_custom,
            ))

        session.decision_points = merged

    def resolve_decision_point(
        self,
        session_id: str,
        decision_id: str,
        choice: str = "",
        custom: str = "",
    ) -> dict:
        """Resolve a decision point with human choice or custom input."""
        session = self._get(session_id)
        dp = None
        for d in session.decision_points:
            if d.decision_id == decision_id:
                dp = d
                break
        if dp is None:
            raise ValueError(f"Decision point '{decision_id}' not found")

        if custom:
            dp.human_custom = custom
            dp.human_choice = "custom"
        elif choice:
            valid = [o.option_id for o in dp.options]
            if choice not in valid and choice != "custom":
                raise ValueError(f"Invalid choice '{choice}'. Valid: {valid}")
            dp.human_choice = choice
        else:
            raise ValueError("Must provide either 'choice' or 'custom'")

        self._add_event(session, EventType.HUMAN_DECISION, "human", content=f"Decision '{dp.topic}': {choice or 'custom: ' + custom}")
        self.store.update_session(session)
        logger.info("resolve_decision_point: %s resolved with %s", decision_id, choice or "custom")
        return {"action": "resolved", "decision_id": decision_id, "choice": dp.human_choice}

    def submit_optimization(
        self,
        session_id: str,
        agent_id: str,
        description: str,
        impact: str = "",
        tradeoff: str = "",
        complexity_change: str = "",
    ) -> Optimization:
        session = self._get(session_id)
        self._validate_phase(session, DebatePhase.OPTIMIZATION)
        self._validate_agent(session, agent_id)
        self._touch_agent(session, agent_id)

        optimization = Optimization(
            optimization_id=uuid.uuid4().hex[:8],
            session_id=session_id,
            agent_id=agent_id,
            round_number=session.current_round,
            description=description,
            impact=impact,
            tradeoff=tradeoff,
            complexity_change=complexity_change,
        )
        session.optimizations.append(optimization)
        self._add_event(session, EventType.OPTIMIZATION, agent_id, content=f"Optimization: {description[:100]}...")
        self.store.update_session(session)
        self._check_phase_completion(session)
        return optimization

    def submit_devils_advocate(
        self,
        session_id: str,
        agent_id: str,
        failure_modes: list[str],
        risk_score: float = 0.5,
        mitigation: str = "",
    ) -> DevilsAdvocate:
        session = self._get(session_id)
        self._validate_phase(session, DebatePhase.DEVILS_ADVOCATE)
        self._validate_agent(session, agent_id)
        self._touch_agent(session, agent_id)

        da = DevilsAdvocate(
            da_id=uuid.uuid4().hex[:8],
            session_id=session_id,
            agent_id=agent_id,
            round_number=session.current_round,
            failure_modes=failure_modes,
            risk_score=risk_score,
            mitigation=mitigation,
        )
        session.devils_advocates.append(da)
        self._add_event(session, EventType.RISK, agent_id, content=f"Devil's advocate: {len(failure_modes)} failure modes, risk={risk_score}")
        self.store.update_session(session)
        self._check_phase_completion(session)
        return da

    def cast_consensus_vote(
        self,
        session_id: str,
        agent_id: str,
        vote_type: VoteType,
        comment: str = "",
    ) -> ConsensusVote:
        session = self._get(session_id)
        self._validate_phase(session, DebatePhase.CONSENSUS)
        self._validate_agent(session, agent_id)
        self._touch_agent(session, agent_id)

        existing = [v for v in session.consensus_votes if v.agent_id == agent_id and v.round_number == session.current_round]
        if existing:
            raise ValueError(f"Agent '{agent_id}' already voted in round {session.current_round}")

        vote = ConsensusVote(
            vote_id=uuid.uuid4().hex[:8],
            session_id=session_id,
            agent_id=agent_id,
            round_number=session.current_round,
            vote_type=vote_type,
            comment=comment,
        )
        session.consensus_votes.append(vote)
        self._add_event(session, EventType.CONSENSUS_VOTE, agent_id, content=f"Voted: {vote_type.value}")
        self.store.update_session(session)
        self._check_consensus(session)
        return vote

    def advance_phase(self, session_id: str) -> dict:
        session = self._get(session_id)

        if session.status == SessionStatus.HUMAN_REVIEW:
            raise ValueError("Cannot manually advance while session is in HUMAN_REVIEW. Resolve pending decisions first.")

        current_idx = PHASE_ORDER.index(session.current_phase)

        if current_idx >= len(PHASE_ORDER) - 1:
            return {"error": "Already at final phase (consensus). Use cast_consensus_vote instead."}

        next_phase = PHASE_ORDER[current_idx + 1]
        session.current_phase = next_phase
        session.status = SessionStatus(next_phase.value)

        if next_phase == DebatePhase.DEVILS_ADVOCATE:
            session.devils_advocate_agent = random.choice([a.agent_id for a in session.agents])

        if next_phase == DebatePhase.PROPOSAL:
            self._assign_perspectives(session)

        self._add_event(session, EventType.SYSTEM_EVENT, "system", content=f"Phase advanced to {next_phase.value}")
        self.store.update_session(session)

        return {
            "session_id": session_id,
            "phase": next_phase.value,
            "round": session.current_round,
            "instruction": PHASE_DESCRIPTIONS[next_phase],
            "devils_advocate_agent": session.devils_advocate_agent if next_phase == DebatePhase.DEVILS_ADVOCATE else None,
            "perspectives": {a.agent_id: a.current_perspective for a in session.agents} if next_phase == DebatePhase.PROPOSAL else None,
        }

    def advance_round(self, session_id: str) -> dict:
        session = self._get(session_id)
        session.current_round += 1
        session.current_phase = DebatePhase.CRITIC
        session.status = SessionStatus.CRITIC
        session.devils_advocate_agent = ""

        self._add_event(session, EventType.SYSTEM_EVENT, "system", content=f"Advanced to round {session.current_round}")
        self.store.update_session(session)

        if session.current_round >= session.max_rounds:
            session.status = SessionStatus.HUMAN_REVIEW
            self._add_event(session, EventType.SYSTEM_EVENT, "system", content="Max rounds reached, moved to human review")
            self.store.update_session(session)
            return {"action": "human_review", "reason": "Maximum rounds reached"}

        return {
            "session_id": session_id,
            "round": session.current_round,
            "phase": DebatePhase.CRITIC.value,
            "instruction": PHASE_DESCRIPTIONS[DebatePhase.CRITIC],
        }

    def raise_question(
        self,
        session_id: str,
        agent_id: str,
        question: str,
        options: list[dict] | None = None,
    ) -> PendingQuestion:
        session = self._get(session_id)
        self._validate_agent(session, agent_id)
        self._touch_agent(session, agent_id)

        opt_models = []
        if options:
            for o in options:
                opt_models.append(QuestionOption(label=o.get("label", ""), description=o.get("description", "")))
        if not any(o.label.lower() == "other" for o in opt_models):
            opt_models.append(QuestionOption(label="Other", description="Custom input"))

        pq = PendingQuestion(
            question_id=uuid.uuid4().hex[:8],
            session_id=session_id,
            asked_by=agent_id,
            question=question,
            options=opt_models,
        )
        session.pending_questions.append(pq)
        self._add_event(session, EventType.QUESTION, agent_id, content=question)
        self.store.update_session(session)
        return pq

    def resolve_question(
        self,
        session_id: str,
        question_id: str,
        human_choice: str,
    ) -> None:
        session = self._get(session_id)
        for q in session.pending_questions:
            if q.question_id == question_id:
                q.resolved = True
                q.human_choice = human_choice
                q.resolution = human_choice
                break
        self._add_event(session, EventType.HUMAN_DECISION, "human", content=f"Question resolved: {human_choice}")
        self.store.update_session(session)

    def get_pending_questions(self, session_id: str) -> list[PendingQuestion]:
        session = self._get(session_id)
        return [q for q in session.pending_questions if not q.resolved]

    def request_human_review(self, session_id: str, reason: str) -> None:
        session = self._get(session_id)
        session.metadata["human_review_reason"] = reason
        session.status = SessionStatus.HUMAN_REVIEW
        self._add_event(session, EventType.HUMAN_DECISION, "system", content=f"Human review requested: {reason}")
        self.store.update_session(session)

    def human_approve(self, session_id: str, approver: str, comment: str = "") -> None:
        session = self._get(session_id)
        if session.status != SessionStatus.HUMAN_REVIEW:
            raise ValueError("Session is not in human review state")
        session.metadata["human_approver"] = approver
        session.metadata["human_approval_comment"] = comment
        session.status = SessionStatus.COMPLETED
        session.completed_at = datetime.now(timezone.utc).isoformat()
        self._add_event(session, EventType.HUMAN_DECISION, approver, content=f"Approved: {comment}")
        self.store.update_session(session)

    def human_reject(self, session_id: str, approver: str, reason: str) -> None:
        session = self._get(session_id)
        if session.status != SessionStatus.HUMAN_REVIEW:
            raise ValueError("Session is not in human review state")
        session.metadata["human_reject_reason"] = reason
        session.metadata["human_reject_approver"] = approver
        session.current_round += 1
        session.current_phase = DebatePhase.PROPOSAL
        session.status = SessionStatus.PROPOSAL
        self._assign_perspectives(session)
        self._add_event(session, EventType.HUMAN_DECISION, approver, content=f"Rejected, starting new round {session.current_round} from PROPOSAL: {reason}")
        self.store.update_session(session)

    def human_override(self, session_id: str, approver: str, decision: str, rationale: str) -> None:
        session = self._get(session_id)
        if session.status == SessionStatus.ARCHIVED:
            raise ValueError("Cannot override an archived session")
        session.metadata["human_override"] = {"decision": decision, "rationale": rationale, "approver": approver}
        session.status = SessionStatus.COMPLETED
        session.completed_at = datetime.now(timezone.utc).isoformat()
        self._add_event(session, EventType.HUMAN_DECISION, approver, content=f"Override decision: {decision}. Rationale: {rationale}")
        self.store.update_session(session)

    def submit_human_vote(self, session_id: str, approver: str, vote_type: str, comment: str = "") -> dict[str, Any]:
        session = self._get(session_id)
        if session.status != SessionStatus.HUMAN_REVIEW:
            raise ValueError("Session is not in human review state")
        vote = HumanVote(
            vote_id=uuid.uuid4().hex[:8],
            session_id=session_id,
            approver=approver,
            vote_type=VoteType(vote_type),
            comment=comment,
        )
        session.human_votes.append(vote)
        self._add_event(session, EventType.HUMAN_DECISION, approver, content=f"Human vote: {vote_type}. {comment}")
        # Aggregate votes: if majority (>>1/2) agree, complete session
        agree_count = sum(1 for v in session.human_votes if v.vote_type == VoteType.AGREE)
        total = len(session.human_votes)
        if total >= 2 and agree_count > total / 2:
            session.status = SessionStatus.COMPLETED
            session.completed_at = datetime.now(timezone.utc).isoformat()
            self._add_event(session, EventType.SYSTEM_EVENT, "system", content=f"Human review completed by majority vote ({agree_count}/{total})")
        self.store.update_session(session)
        return {
            "vote_id": vote.vote_id,
            "total_votes": total,
            "agree_count": agree_count,
            "session_status": session.status.value,
        }

    def archive_session(self, session_id: str) -> dict:
        session = self._get(session_id)
        if session.status != SessionStatus.COMPLETED:
            raise ValueError("Only completed sessions can be archived")
        archive_path = self.store.archive_session(session_id)
        self._add_event(session, EventType.SYSTEM_EVENT, "system", content="Session archived and working data cleaned up")
        return {
            "session_id": session_id,
            "archive_path": str(archive_path) if archive_path else None,
            "status": "archived",
        }

    def pause_session(self, session_id: str) -> dict:
        """Pause a session. Agents cannot submit while paused."""
        session = self._get(session_id)
        if session.status == SessionStatus.PAUSED:
            raise ValueError("Session is already paused")
        if session.status in (SessionStatus.COMPLETED, SessionStatus.ARCHIVED):
            raise ValueError(f"Cannot pause {session.status.value} session")
        previous_status = session.status
        session.metadata["paused_from_status"] = previous_status.value
        session.status = SessionStatus.PAUSED
        self._add_event(session, EventType.SYSTEM_EVENT, "system", content="Session paused")
        self.store.update_session(session)
        logger.info("pause_session: session %s paused from %s", session_id, previous_status.value)
        return {"session_id": session_id, "status": "paused", "previous_status": previous_status.value}

    def resume_session(self, session_id: str) -> dict:
        """Resume a paused session."""
        session = self._get(session_id)
        if session.status != SessionStatus.PAUSED:
            raise ValueError("Session is not paused")
        previous_status = session.metadata.pop("paused_from_status", session.current_phase.value)
        try:
            session.status = SessionStatus(previous_status)
        except ValueError:
            session.status = SessionStatus(session.current_phase.value)
        self._add_event(session, EventType.SYSTEM_EVENT, "system", content=f"Session resumed from {previous_status}")
        self.store.update_session(session)
        logger.info("resume_session: session %s resumed to %s", session_id, previous_status)
        return {"session_id": session_id, "status": session.status.value, "resumed_from": previous_status}

    def revert_to_event(self, session_id: str, event_id: str) -> dict:
        """Revert session state to a specific event point using the event log.

        Limitations (basic implementation):
        - Truncates data lists by created_at rather than deterministic replay.
        - Derived state (merged assumptions, perspectives, etc.) is cleared and
          must be regenerated by advancing through phases again.
        - Status inference relies on heuristics over remaining system events;
          it may not perfectly reproduce the exact status at the target event.
        - A full deterministic replay would require snapshotting session state
          after each event or replaying every event's side effects precisely.
        """
        session = self._get(session_id)

        target_index = None
        for i, event in enumerate(session.events):
            if event.event_id == event_id:
                target_index = i
                break

        if target_index is None:
            raise ValueError(f"Event '{event_id}' not found in session")

        target_event = session.events[target_index]
        target_time = target_event.created_at

        # Truncate event log
        session.events = session.events[:target_index + 1]

        # Truncate data lists by created_at
        session.assumptions = [a for a in session.assumptions if a.created_at <= target_time]
        session.refined_requirements = [r for r in session.refined_requirements if r.created_at <= target_time]
        session.proposals = [p for p in session.proposals if p.created_at <= target_time]
        session.challenges = [c for c in session.challenges if c.created_at <= target_time]
        session.revisions = [r for r in session.revisions if r.created_at <= target_time]
        session.optimizations = [o for o in session.optimizations if o.created_at <= target_time]
        session.devils_advocates = [d for d in session.devils_advocates if d.created_at <= target_time]
        session.consensus_votes = [v for v in session.consensus_votes if v.created_at <= target_time]
        session.pending_questions = [q for q in session.pending_questions if q.created_at <= target_time]
        session.requirement_deltas = [d for d in session.requirement_deltas if d.created_at <= target_time]

        # Clear derived state that can be regenerated
        session.merged_assumptions = []
        session.clarify_refine_submitted = []
        session.devils_advocate_agent = ""
        session.novelty_scores = []

        # Reset phase and round
        session.current_phase = target_event.phase
        session.current_round = target_event.round_number

        # Infer status from remaining events
        session.status = SessionStatus(target_event.phase.value)
        for event in reversed(session.events):
            if event.event_type == EventType.SYSTEM_EVENT:
                content = event.content
                if "waiting for human approval" in content or "moved to human review" in content or "escalated to human review" in content:
                    session.status = SessionStatus.HUMAN_REVIEW
                    break
                if "Consensus reached" in content or "Full consensus" in content:
                    session.status = SessionStatus.COMPLETED
                    break
                if "Auto-advanced" in content:
                    try:
                        session.status = SessionStatus(session.current_phase.value)
                    except ValueError:
                        session.status = SessionStatus.CREATED
                    break

        if session.status != SessionStatus.COMPLETED:
            session.completed_at = None
        if session.status != SessionStatus.ARCHIVED:
            session.archived_at = None

        self._add_event(session, EventType.SYSTEM_EVENT, "system", content=f"Reverted to event {event_id}")
        self.store.update_session(session)
        logger.info("revert_to_event: session %s reverted to event %s", session_id, event_id)
        return {"session_id": session_id, "reverted_to": event_id, "phase": session.current_phase.value, "status": session.status.value}

    def get_session_flow(self, session_id: str) -> dict:
        session = self._get(session_id)

        key_decisions = []
        for event in session.events:
            if event.event_type == EventType.HUMAN_DECISION:
                key_decisions.append({
                    "type": "human_decision",
                    "phase": event.phase.value,
                    "content": event.content,
                    "timestamp": event.created_at,
                })
            elif event.event_type == EventType.SYSTEM_EVENT and "Auto-advanced" in event.content:
                key_decisions.append({
                    "type": "phase_transition",
                    "content": event.content,
                    "timestamp": event.created_at,
                })

        assumption_decisions = []
        for group in session.merged_assumptions:
            for a in group.assumptions:
                if a.human_choice:
                    assumption_decisions.append({
                        "dimension": group.dimension,
                        "assumption": a.assumption,
                        "human_choice": a.human_choice,
                        "divergent": group.divergent,
                    })

        round_summaries = []
        for r in range(1, session.current_round + 1):
            proposals = [p for p in session.proposals if p.round_number == r]
            challenges = [c for c in session.challenges if c.round_number == r]
            revisions = [rv for rv in session.revisions if rv.round_number == r]
            votes = [v for v in session.consensus_votes if v.round_number == r]
            round_summaries.append({
                "round": r,
                "proposals": len(proposals),
                "challenges": len(challenges),
                "revisions": len(revisions),
                "consensus_votes": {
                    "agree": sum(1 for v in votes if v.vote_type == VoteType.AGREE),
                    "disagree": sum(1 for v in votes if v.vote_type == VoteType.DISAGREE),
                    "needs_clarification": sum(1 for v in votes if v.vote_type == VoteType.NEEDS_CLARIFICATION),
                },
            })

        event_timeline = []
        prev_phase = DebatePhase.CREATED.value
        for event in session.events:
            curr_phase = event.phase.value
            if curr_phase != prev_phase:
                event_timeline.append({
                    "from_phase": prev_phase,
                    "to_phase": curr_phase,
                    "timestamp": event.created_at,
                })
                prev_phase = curr_phase

        return {
            "session_id": session.session_id,
            "title": session.title,
            "status": session.status.value,
            "current_phase": session.current_phase.value,
            "current_round": session.current_round,
            "clarify_round": session.clarify_round,
            "requirement_refined": session.requirement.is_refined if session.requirement else False,
            "assumption_decisions": assumption_decisions,
            "key_decisions": key_decisions,
            "round_summaries": round_summaries,
            "total_events": len(session.events),
            "unresolved_questions": len([q for q in session.pending_questions if not q.resolved]),
            "requirement_deltas_count": len(session.requirement_deltas),
            "requirement_deltas": [
                {
                    "delta_id": d.delta_id,
                    "parent_delta_id": d.parent_delta_id,
                    "problem_statement": d.problem_statement,
                    "created_at": d.created_at,
                }
                for d in session.requirement_deltas
            ],
            "event_timeline": event_timeline,
        }

    def get_session_summary(self, session_id: str) -> dict:
        session = self._get(session_id)
        round_votes = [v for v in session.consensus_votes if v.round_number == session.current_round]
        unresolved = [q for q in session.pending_questions if not q.resolved]

        return {
            "session_id": session.session_id,
            "title": session.title,
            "status": session.status.value,
            "current_phase": session.current_phase.value,
            "current_round": session.current_round,
            "clarify_round": session.clarify_round,
            "min_rounds": session.min_rounds,
            "max_rounds": session.max_rounds,
            "agents": [{"id": a.agent_id, "name": a.name, "perspective": a.current_perspective} for a in session.agents],
            "requirement": session.requirement.model_dump() if session.requirement else None,
            "assumptions_count": len(session.assumptions),
            "merged_assumptions_count": len(session.merged_assumptions),
            "proposals_count": len(session.proposals),
            "challenges_count": len(session.challenges),
            "revisions_count": len(session.revisions),
            "optimizations_count": len(session.optimizations),
            "devils_advocates_count": len(session.devils_advocates),
            "consensus_votes": [v.model_dump() for v in round_votes],
            "unresolved_questions": len(unresolved),
            "total_events": len(session.events),
            "devils_advocate_agent": session.devils_advocate_agent,
            "novelty_scores": session.novelty_scores[-3:] if session.novelty_scores else [],
            "requirement_deltas_count": len(session.requirement_deltas),
            "requirement_deltas": [
                {
                    "delta_id": d.delta_id,
                    "parent_delta_id": d.parent_delta_id,
                    "problem_statement": d.problem_statement,
                    "created_at": d.created_at,
                }
                for d in session.requirement_deltas
            ],
        }

    def get_phase_context(self, session_id: str, agent_id: str) -> dict:
        session = self._get(session_id)
        self._validate_agent(session, agent_id)
        phase = session.current_phase
        context: dict = {
            "phase": phase.value,
            "round": session.current_round,
            "clarify_round": session.clarify_round,
            "instruction": PHASE_DESCRIPTIONS[phase],
            "requirement": session.requirement.model_dump() if session.requirement else None,
        }

        if phase == DebatePhase.CLARIFY_IDENTIFY:
            context["dimensions"] = ASSUMPTION_DIMENSIONS
            context["your_assumptions"] = [a.model_dump() for a in session.assumptions if a.agent_id == agent_id]
            context["submitted_agents"] = list({a.agent_id for a in session.assumptions})
            context["total_agents"] = len(session.agents)

        elif phase == DebatePhase.CLARIFY_REFINE:
            context["merged_assumptions"] = [g.model_dump() for g in session.merged_assumptions]
            context["your_supplements"] = []

        elif phase == DebatePhase.CLARIFY_REVIEW:
            context["merged_assumptions"] = [g.model_dump() for g in session.merged_assumptions]
            context["divergent_assumptions"] = [g.model_dump() for g in session.merged_assumptions if g.divergent]

        elif phase == DebatePhase.CLARIFY_REWRITE:
            context["merged_assumptions"] = [g.model_dump() for g in session.merged_assumptions]
            context["human_choices"] = {
                a.assumption_id: a.human_choice
                for g in session.merged_assumptions
                for a in g.assumptions
                if a.human_choice
            }
            context["your_refined_requirement"] = None
            for r in session.refined_requirements:
                if r.agent_id == agent_id:
                    context["your_refined_requirement"] = r.model_dump()
                    break

        elif phase == DebatePhase.PROPOSAL:
            agent = next(a for a in session.agents if a.agent_id == agent_id)
            context["perspective"] = agent.current_perspective
            context["perspective_description"] = PERSPECTIVE_DESCRIPTIONS.get(agent.current_perspective, "")
            context["other_proposals_visible"] = False
            context["your_existing_proposal"] = None
            for p in session.proposals:
                if p.agent_id == agent_id and p.round_number == session.current_round:
                    context["your_existing_proposal"] = p.model_dump()
                    break

        elif phase == DebatePhase.CRITIC:
            context["proposals"] = [p.model_dump() for p in session.proposals if p.round_number == session.current_round]
            context["your_challenges"] = [c.model_dump() for c in session.challenges if c.agent_id == agent_id and c.round_number == session.current_round]

        elif phase == DebatePhase.REVISION:
            context["challenges_against_you"] = [c.model_dump() for c in session.challenges if c.target_agent_id == agent_id and c.round_number == session.current_round]
            context["your_revisions"] = [r.model_dump() for r in session.revisions if r.agent_id == agent_id and r.round_number == session.current_round]

        elif phase == DebatePhase.OPTIMIZATION:
            context["revisions"] = [r.model_dump() for r in session.revisions if r.round_number == session.current_round]
            context["your_optimizations"] = [o.model_dump() for o in session.optimizations if o.agent_id == agent_id and o.round_number == session.current_round]

        elif phase == DebatePhase.DEVILS_ADVOCATE:
            context["is_devils_advocate"] = session.devils_advocate_agent == agent_id
            context["current_design_summary"] = self._build_design_summary(session)
            context["your_da_submission"] = None
            for da in session.devils_advocates:
                if da.agent_id == agent_id and da.round_number == session.current_round:
                    context["your_da_submission"] = da.model_dump()
                    break

        elif phase == DebatePhase.CONSENSUS:
            context["design_summary"] = self._build_design_summary(session)
            context["your_vote"] = None
            for v in session.consensus_votes:
                if v.agent_id == agent_id and v.round_number == session.current_round:
                    context["your_vote"] = v.model_dump()
                    break
            context["votes_cast"] = len([v for v in session.consensus_votes if v.round_number == session.current_round])
            context["total_agents"] = len(session.agents)

        return context

    def _add_event(
        self,
        session: Session,
        event_type: EventType,
        source_agent: str,
        content: str,
        target_agent: str = "",
    ) -> None:
        event = Event(
            event_id=uuid.uuid4().hex[:10],
            session_id=session.session_id,
            round_number=session.current_round,
            phase=session.current_phase,
            event_type=event_type,
            source_agent=source_agent,
            target_agent=target_agent,
            content=content,
        )
        session.events.append(event)
        event_bus.emit(session.session_id, event_type.value, {
            "event_id": event.event_id,
            "session_id": session.session_id,
            "round": session.current_round,
            "phase": session.current_phase.value,
            "source_agent": source_agent,
            "target_agent": target_agent,
            "content": content,
        })

    def _validate_phase(self, session: Session, expected: DebatePhase) -> None:
        if session.status == SessionStatus.PAUSED:
            raise ValueError("Session is paused. Resume before submitting.")
        if session.current_phase != expected:
            raise ValueError(f"Expected phase '{expected.value}', but session is in '{session.current_phase.value}'")

    def _validate_agent(self, session: Session, agent_id: str) -> None:
        if not any(a.agent_id == agent_id for a in session.agents):
            raise ValueError(f"Agent '{agent_id}' is not registered in session '{session.session_id}'")

    def _touch_agent(self, session: Session, agent_id: str) -> None:
        for a in session.agents:
            if a.agent_id == agent_id:
                a.last_active_at = datetime.now(timezone.utc).isoformat()
                a.is_active = True
                break

    def _mark_inactive_agents(self, session: Session) -> list[str]:
        now = datetime.now(timezone.utc)
        inactive_ids: list[str] = []
        for a in session.agents:
            if not a.is_active:
                continue
            try:
                last = datetime.fromisoformat(a.last_active_at)
                if (now - last).total_seconds() > AGENT_INACTIVE_TIMEOUT_SECONDS:
                    a.is_active = False
                    inactive_ids.append(a.agent_id)
            except (ValueError, TypeError):
                pass
        return inactive_ids

    def _active_agent_count(self, session: Session) -> int:
        return len([a for a in session.agents if a.is_active])

    def heartbeat(self, session_id: str, agent_id: str) -> dict[str, Any]:
        hb_logger = logging.getLogger("designdoc_mcp.heartbeat")
        session = self._get(session_id)
        self._validate_agent(session, agent_id)
        self._touch_agent(session, agent_id)
        self.store.update_session(session)
        hb_logger.info("heartbeat: session=%s agent=%s phase=%s round=%d", session_id, agent_id, session.current_phase.value, session.current_round)
        return {
            "session_id": session_id,
            "agent_id": agent_id,
            "status": "ok",
            "phase": session.current_phase.value,
            "round": session.current_round,
        }

    def check_stalled(self, session_id: str) -> dict[str, Any]:
        session = self._get(session_id)
        inactive_ids = self._mark_inactive_agents(session)

        if inactive_ids:
            self._add_event(
                session, EventType.SYSTEM_EVENT, "system",
                content=f"Agents marked inactive (timeout {AGENT_INACTIVE_TIMEOUT_SECONDS}s): {', '.join(inactive_ids)}",
            )

        active_count = self._active_agent_count(session)
        total_count = len(session.agents)

        stalled = False
        can_auto_advance = False

        blocking_phases = {
            DebatePhase.CLARIFY_IDENTIFY,
            DebatePhase.PROPOSAL,
            DebatePhase.CRITIC,
            DebatePhase.REVISION,
            DebatePhase.OPTIMIZATION,
            DebatePhase.CONSENSUS,
        }

        if session.current_phase in blocking_phases and inactive_ids:
            if active_count >= 1:
                can_auto_advance = True
            else:
                stalled = True

        if can_auto_advance:
            self._check_phase_completion(session, force_active_only=True)

        if stalled and session.current_phase == DebatePhase.CONSENSUS:
            session.status = SessionStatus.HUMAN_REVIEW
            self._add_event(session, EventType.SYSTEM_EVENT, "system", content="All agents inactive during consensus, escalated to human review")

        self.store.update_session(session)

        return {
            "session_id": session_id,
            "total_agents": total_count,
            "active_agents": active_count,
            "inactive_agents": inactive_ids,
            "stalled": stalled,
            "can_auto_advance": can_auto_advance,
            "current_phase": session.current_phase.value,
        }

    def _check_phase_completion(self, session: Session, force_active_only: bool = False) -> None:
        phase = session.current_phase
        agent_count = len(session.agents)
        active_count = self._active_agent_count(session)
        use_count = active_count if force_active_only else agent_count

        if session.status == SessionStatus.HUMAN_REVIEW:
            logger.debug("_check_phase_completion: session in HUMAN_REVIEW, skipping auto-advance")
            return

        complete = False

        if phase == DebatePhase.CLARIFY_IDENTIFY:
            submitted_agents = {a.agent_id for a in session.assumptions if a.clarify_round == session.clarify_round}
            if len(submitted_agents) >= use_count:
                complete = True
                logger.info("Phase CLARIFY_IDENTIFY complete: %d/%d agents submitted", len(submitted_agents), use_count)

        elif phase == DebatePhase.CLARIFY_REFINE:
            submitted_count = len(session.clarify_refine_submitted)
            if submitted_count >= use_count:
                complete = True
                logger.info("Phase CLARIFY_REFINE complete: %d/%d agents submitted", submitted_count, use_count)

        elif phase == DebatePhase.CLARIFY_REVIEW:
            pass

        elif phase == DebatePhase.CLARIFY_REWRITE:
            submitted_agents = {r.agent_id for r in session.refined_requirements}
            if len(submitted_agents) >= use_count:
                complete = True
                logger.info("Phase CLARIFY_REWRITE complete: %d/%d agents submitted (waiting for human approval)", len(submitted_agents), use_count)

        elif phase == DebatePhase.PROPOSAL:
            submitted = len([p for p in session.proposals if p.round_number == session.current_round])
            if submitted >= use_count:
                complete = True
                logger.info("Phase PROPOSAL complete: %d/%d proposals submitted", submitted, use_count)

        elif phase == DebatePhase.CRITIC:
            submitted = len([c for c in session.challenges if c.round_number == session.current_round])
            if submitted >= use_count:
                complete = True
                logger.info("Phase CRITIC complete: %d/%d challenges submitted", submitted, use_count)

        elif phase == DebatePhase.REVISION:
            submitted = len([r for r in session.revisions if r.round_number == session.current_round])
            if submitted >= use_count:
                complete = True
                logger.info("Phase REVISION complete: %d/%d revisions submitted", submitted, use_count)

        elif phase == DebatePhase.OPTIMIZATION:
            submitted = len([o for o in session.optimizations if o.round_number == session.current_round])
            if submitted >= use_count:
                complete = True
                logger.info("Phase OPTIMIZATION complete: %d/%d optimizations submitted", submitted, use_count)

        elif phase == DebatePhase.DEVILS_ADVOCATE:
            da_submitted = len([d for d in session.devils_advocates if d.round_number == session.current_round])
            if da_submitted >= 1:
                complete = True
                logger.info("Phase DEVILS_ADVOCATE complete: %d DA submitted", da_submitted)

        elif phase == DebatePhase.CONSENSUS:
            round_votes = [v for v in session.consensus_votes if v.round_number == session.current_round]
            if force_active_only and active_count < 2:
                session.status = SessionStatus.HUMAN_REVIEW
                self._add_event(session, EventType.SYSTEM_EVENT, "system", content="Too few active agents for consensus, escalated to human review")
                self.store.update_session(session)
                return
            if len(round_votes) >= use_count and use_count > 0:
                self._check_consensus(session)
                return

        if complete:
            logger.info("Auto-advancing from %s", phase.value)
            self._auto_advance(session)

    def _auto_advance(self, session: Session) -> None:
        # CLARIFY_REWRITE 完成后不自动推进到 PROPOSAL，需等待人类批准
        if session.current_phase == DebatePhase.CLARIFY_REWRITE:
            session.status = SessionStatus.HUMAN_REVIEW
            session.metadata["human_review_reason"] = "All refined requirements submitted. Human must approve one before proceeding to PROPOSAL."
            self._add_event(session, EventType.SYSTEM_EVENT, "system", content="All refined requirements submitted, waiting for human approval")
            self.store.update_session(session)
            return

        current_idx = PHASE_ORDER.index(session.current_phase)
        if current_idx < len(PHASE_ORDER) - 1:
            next_phase = PHASE_ORDER[current_idx + 1]
            session.current_phase = next_phase
            session.status = SessionStatus(next_phase.value)

            if next_phase == DebatePhase.CLARIFY_REFINE:
                self._merge_assumptions(session)

            if next_phase == DebatePhase.REVISION:
                # Merge decision points from Critic phase before moving to Revision
                self._merge_decision_points(session)

            if next_phase == DebatePhase.CLARIFY_REVIEW:
                pass

            if next_phase == DebatePhase.DEVILS_ADVOCATE:
                session.devils_advocate_agent = random.choice([a.agent_id for a in session.agents])

            if next_phase == DebatePhase.PROPOSAL:
                self._assign_perspectives(session)

            self._add_event(session, EventType.SYSTEM_EVENT, "system", content=f"Auto-advanced to {next_phase.value}")
            self.store.update_session(session)

            # 为新阶段的所有活跃 agent 创建任务
            self._push_tasks_for_phase(session)

    def _check_consensus(self, session: Session) -> None:
        round_votes = [v for v in session.consensus_votes if v.round_number == session.current_round]
        if len(round_votes) < len(session.agents):
            return

        agrees = sum(1 for v in round_votes if v.vote_type == VoteType.AGREE)
        disagrees = sum(1 for v in round_votes if v.vote_type == VoteType.DISAGREE)
        needs_clarification = sum(1 for v in round_votes if v.vote_type == VoteType.NEEDS_CLARIFICATION)
        abstains = sum(1 for v in round_votes if v.vote_type == VoteType.ABSTAIN)

        if agrees == len(session.agents):
            session.status = SessionStatus.COMPLETED
            session.completed_at = datetime.now(timezone.utc).isoformat()
            self._add_event(session, EventType.SYSTEM_EVENT, "system", content="Full consensus reached!")
        elif agrees > 0 and (disagrees + needs_clarification) == 0:
            session.status = SessionStatus.COMPLETED
            session.completed_at = datetime.now(timezone.utc).isoformat()
            self._add_event(session, EventType.SYSTEM_EVENT, "system", content=f"Consensus reached with {abstains} abstention(s)")
        elif disagrees >= CONSENSUS_SEVERE_DISAGREEMENT_THRESHOLD or needs_clarification >= CONSENSUS_SEVERE_DISAGREEMENT_THRESHOLD:
            session.status = SessionStatus.HUMAN_REVIEW
            session.metadata["human_review_reason"] = f"Consensus failed: {disagrees} disagree, {needs_clarification} need clarification"
            self._add_event(session, EventType.SYSTEM_EVENT, "system", content="Consensus failed, moved to human review")
        elif (disagrees + needs_clarification) >= CONSENSUS_PARTIAL_AGREEMENT_MIN and agrees >= CONSENSUS_PARTIAL_AGREEMENT_MIN:
            session.status = SessionStatus.HUMAN_REVIEW
            session.metadata["human_review_reason"] = f"Partial consensus: {agrees} agree, {disagrees} disagree, {needs_clarification} need clarification, {abstains} abstain"
            self._add_event(session, EventType.SYSTEM_EVENT, "system", content="Partial consensus, moved to human review")

        self.store.update_session(session)

    def _build_design_summary(self, session: Session) -> str:
        parts = []
        if session.proposals:
            latest = [p for p in session.proposals if p.round_number == session.current_round]
            if not latest:
                latest = session.proposals[-len(session.agents):]
            for p in latest:
                parts.append(f"[{p.agent_id}] Architecture: {p.architecture}")
                if p.tech_stack:
                    parts.append(f"  Tech Stack: {p.tech_stack}")
                if p.perspective:
                    parts.append(f"  Perspective: {p.perspective}")
        if session.revisions:
            latest_rev = [r for r in session.revisions if r.round_number == session.current_round]
            for r in latest_rev:
                parts.append(f"[{r.agent_id}] Revised: {r.changed_design[:200]}")
        return "\n".join(parts) if parts else "No proposals yet."

    # ------------------------------------------------------------------
    # Blocking-pull protocol: task distribution
    # ------------------------------------------------------------------

    def _push_tasks_for_phase(self, session: Session) -> None:
        """为当前阶段的所有活跃 agent 创建任务"""
        phase = session.current_phase
        task_type_map: dict[DebatePhase, str] = {
            DebatePhase.CLARIFY_IDENTIFY: "submit_assumptions",
            DebatePhase.CLARIFY_REFINE: "supplement_assumption_options",
            DebatePhase.CLARIFY_REWRITE: "submit_refined_requirement",
            DebatePhase.PROPOSAL: "submit_proposal",
            DebatePhase.CRITIC: "submit_challenge",
            DebatePhase.REVISION: "submit_revision",
            DebatePhase.OPTIMIZATION: "submit_optimization",
            DebatePhase.DEVILS_ADVOCATE: "submit_devils_advocate",
            DebatePhase.CONSENSUS: "cast_consensus_vote",
        }
        task_type = task_type_map.get(phase)
        if not task_type:
            return  # wait phases (clarify_review, human_review)

        for agent in session.agents:
            if not agent.is_active:
                continue
            # Devils advocate only for designated agent
            if phase == DebatePhase.DEVILS_ADVOCATE and agent.agent_id != session.devils_advocate_agent:
                continue
            self.store.push_task(
                session_id=session.session_id,
                agent_id=agent.agent_id,
                task_type=task_type,
                phase=phase.value,
                round_number=session.current_round,
                payload=self._build_task_payload(session, agent, task_type),
            )
        logger.info(
            "push_tasks_for_phase: session=%s phase=%s task_type=%s agents=%d",
            session.session_id, phase.value, task_type,
            len([a for a in session.agents if a.is_active]),
        )

    def _build_task_payload(self, session: Session, agent: AgentInfo, task_type: str) -> dict:
        """构建任务上下文，包含 agent 需要的所有信息"""
        payload: dict[str, Any] = {
            "phase": session.current_phase.value,
            "round": session.current_round,
            "clarify_round": session.clarify_round,
            "instruction": PHASE_DESCRIPTIONS.get(session.current_phase, ""),
        }
        if session.requirement:
            payload["requirement"] = session.requirement.model_dump()
        if agent.current_perspective:
            payload["perspective"] = agent.current_perspective
            payload["perspective_description"] = PERSPECTIVE_DESCRIPTIONS.get(agent.current_perspective, "")

        # Phase-specific context
        if task_type == "submit_challenge":
            proposals = [
                p.model_dump() for p in session.proposals
                if p.round_number == session.current_round and p.agent_id != agent.agent_id
            ]
            payload["proposals_to_challenge"] = proposals
        elif task_type == "submit_revision":
            challenges_against = [
                c.model_dump() for c in session.challenges
                if c.target_agent_id == agent.agent_id and c.round_number == session.current_round
            ]
            payload["challenges_against_you"] = challenges_against
        elif task_type == "submit_optimization":
            revisions = [
                r.model_dump() for r in session.revisions
                if r.round_number == session.current_round
            ]
            payload["revisions"] = revisions
        elif task_type == "submit_devils_advocate":
            payload["design_summary"] = self._build_design_summary(session)
        elif task_type == "cast_consensus_vote":
            payload["design_summary"] = self._build_design_summary(session)
        elif task_type == "submit_assumptions":
            payload["dimensions"] = ASSUMPTION_DIMENSIONS
        elif task_type == "supplement_assumption_options":
            payload["merged_assumptions"] = [g.model_dump() for g in session.merged_assumptions]
        elif task_type == "submit_refined_requirement":
            payload["merged_assumptions"] = [g.model_dump() for g in session.merged_assumptions]
            payload["human_choices"] = {
                a.assumption_id: a.human_choice
                for g in session.merged_assumptions
                for a in g.assumptions
                if a.human_choice
            }

        return payload

    def wait_for_task_engine(self, session_id: str, agent_id: str, timeout: float = 300.0) -> dict | None:
        """Engine 层的 wait_for_task 实现"""
        session = self._get(session_id)
        self._validate_agent(session, agent_id)
        self._touch_agent(session, agent_id)
        self.store.update_session(session)

        # 先检查是否有 pending 任务
        task = self.store.wait_for_task(agent_id, timeout)
        if task:
            return task

        # 如果没有 pending 任务，检查当前阶段是否需要为该 agent 创建任务
        # （可能是新加入的 agent 或阶段刚推进）
        return None

    def submit_result_engine(self, session_id: str, agent_id: str, task_id: str, result: dict) -> dict:
        """Engine 层的 submit_result 实现

        统一提交接口：标记任务完成，根据 task_type 分发到具体的提交方法，
        检查阶段完成，返回下一个任务。
        """
        session = self._get(session_id)
        self._validate_agent(session, agent_id)
        self._touch_agent(session, agent_id)

        # 标记任务完成
        self.store.complete_task(task_id)

        # 根据 task_type 分发到具体的提交方法
        task_type = result.get("_task_type", "")

        try:
            if task_type == "submit_assumptions":
                assumptions = result.get("assumptions", [])
                self.submit_assumptions(session_id, agent_id, assumptions)
            elif task_type == "supplement_assumption_options":
                supplements = result.get("supplements", [])
                self.supplement_assumption_options(session_id, agent_id, supplements)
            elif task_type == "submit_refined_requirement":
                self.submit_refined_requirement(
                    session_id, agent_id,
                    refined_statement=result.get("refined_statement", ""),
                    constraints=result.get("constraints"),
                    acceptance_criteria=result.get("acceptance_criteria"),
                )
            elif task_type == "submit_proposal":
                self.submit_proposal(
                    session_id, agent_id,
                    architecture=result.get("architecture", ""),
                    tech_stack=result.get("tech_stack", ""),
                    tradeoffs=result.get("tradeoffs", ""),
                    risks=result.get("risks", ""),
                    assumptions=result.get("assumptions", ""),
                    unknowns=result.get("unknowns", ""),
                    raw_content=result.get("raw_content", ""),
                )
            elif task_type == "submit_challenge":
                self.submit_challenge(
                    session_id, agent_id,
                    target_agent_id=result.get("target_agent_id", ""),
                    target_proposal_id=result.get("target_proposal_id", ""),
                    risks=result.get("risks", []),
                    missing_considerations=result.get("missing_considerations", []),
                    alternative_proposal=result.get("alternative_proposal", ""),
                    category=result.get("category", DEFAULT_CHALLENGE_CATEGORY),
                    priority=result.get("priority", DEFAULT_CHALLENGE_PRIORITY),
                    confidence=result.get("confidence", DEFAULT_CONFIDENCE),
                )
            elif task_type == "submit_revision":
                self.submit_revision(
                    session_id, agent_id,
                    accepted_feedback=result.get("accepted_feedback", []),
                    rejected_feedback=result.get("rejected_feedback", []),
                    rejection_reasons=result.get("rejection_reasons", []),
                    changed_design=result.get("changed_design", ""),
                )
            elif task_type == "submit_optimization":
                self.submit_optimization(
                    session_id, agent_id,
                    description=result.get("description", ""),
                    impact=result.get("impact", ""),
                    tradeoff=result.get("tradeoff", ""),
                    complexity_change=result.get("complexity_change", ""),
                )
            elif task_type == "submit_devils_advocate":
                self.submit_devils_advocate(
                    session_id, agent_id,
                    failure_modes=result.get("failure_modes", []),
                    risk_score=result.get("risk_score", 0.5),
                    mitigation=result.get("mitigation", ""),
                )
            elif task_type == "cast_consensus_vote":
                vote_type_str = result.get("vote_type", DEFAULT_VOTE_TYPE)
                self.cast_consensus_vote(
                    session_id, agent_id,
                    vote_type=VoteType(vote_type_str),
                    comment=result.get("comment", ""),
                )
        except ValueError as e:
            logger.warning("submit_result_engine dispatch failed: %s", e)
            return {"status": "error", "message": str(e)}

        # 返回下一个任务
        next_task = self.store.wait_for_task(agent_id, timeout=TASK_POLL_TIMEOUT)
        return next_task or {"status": "no_task"}

    def compare_sessions(self, session_id_a: str, session_id_b: str) -> dict[str, Any]:
        """Compare two sessions and return a structured diff.

        Compares requirements, agent counts, phases, statuses, and key metrics.
        """
        session_a = self._get(session_id_a)
        session_b = self._get(session_id_b)

        req_a = session_a.requirement.problem_statement if session_a.requirement else ""
        req_b = session_b.requirement.problem_statement if session_b.requirement else ""

        return {
            "session_a": {"title": session_a.title, "status": session_a.status.value, "phase": session_a.current_phase.value},
            "session_b": {"title": session_b.title, "status": session_b.status.value, "phase": session_b.current_phase.value},
            "requirements_match": req_a == req_b,
            "agent_count": {"a": len(session_a.agents), "b": len(session_b.agents)},
            "round_count": {"a": session_a.current_round, "b": session_b.current_round},
            "proposal_count": {"a": len(session_a.proposals), "b": len(session_b.proposals)},
            "same_phase": session_a.current_phase == session_b.current_phase,
            "same_status": session_a.status == session_b.status,
        }

    def _get(self, session_id: str) -> Session:
        session = self.store.get_session(session_id)
        if session is None:
            raise ValueError(f"Session '{session_id}' not found")
        return session
