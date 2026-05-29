from __future__ import annotations

import enum
import os
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class DebatePhase(str, enum.Enum):
    CREATED = "created"
    CLARIFY_IDENTIFY = "clarify_identify"
    CLARIFY_REFINE = "clarify_refine"
    CLARIFY_REVIEW = "clarify_review"
    CLARIFY_REWRITE = "clarify_rewrite"
    PROPOSAL = "proposal"
    CRITIC = "critic"
    REVISION = "revision"
    OPTIMIZATION = "optimization"
    DEVILS_ADVOCATE = "devils_advocate"
    CONSENSUS = "consensus"


CLARIFY_PHASES = [
    DebatePhase.CLARIFY_IDENTIFY,
    DebatePhase.CLARIFY_REFINE,
    DebatePhase.CLARIFY_REVIEW,
    DebatePhase.CLARIFY_REWRITE,
]

DEBATE_PHASES = [
    DebatePhase.PROPOSAL,
    DebatePhase.CRITIC,
    DebatePhase.REVISION,
    DebatePhase.OPTIMIZATION,
    DebatePhase.DEVILS_ADVOCATE,
    DebatePhase.CONSENSUS,
]

PHASE_ORDER: list[DebatePhase] = CLARIFY_PHASES + DEBATE_PHASES

PHASE_DESCRIPTIONS: dict[DebatePhase, str] = {
    DebatePhase.CLARIFY_IDENTIFY: "Each agent independently identifies assumptions in the fuzzy requirement. Do NOT read other agents' assumptions. Produce a structured assumption document organized by dimension (data, users, workflow, non-functional, integration). Each assumption must include alternatives for human to choose from.",
    DebatePhase.CLARIFY_REFINE: "System has merged all assumptions. Agents can now supplement alternatives to existing assumptions, but cannot remove or challenge assumptions raised by others. Focus on adding missing options.",
    DebatePhase.CLARIFY_REVIEW: "Human reviews the merged assumption document. For each assumption, human can accept the default or choose an alternative. Divergent assumptions (agents disagree) must be resolved.",
    DebatePhase.CLARIFY_REWRITE: "Based on human choices, agents propose a refined requirement document. The refined requirement replaces the original fuzzy statement.",
    DebatePhase.PROPOSAL: "Each agent independently proposes a solution from their assigned perspective. Agents MUST NOT read other agents' proposals to avoid anchoring bias.",
    DebatePhase.CRITIC: "Agents challenge each other's proposals. Each agent MUST: (1) identify at least 3 risks, 2 missing considerations, and 1 alternative; (2) submit decision_points for key divergences (e.g., database choice, deployment strategy) where agents propose different solutions. Vague agreement like 'I agree' or 'looks good' is FORBIDDEN.",
    DebatePhase.REVISION: "Agents revise their proposals by incorporating valid feedback. Must explicitly state accepted/rejected feedback with reasons. Polite acknowledgment without design changes is FORBIDDEN.",
    DebatePhase.OPTIMIZATION: "Agents propose optimizations: simpler, more stable, cheaper, more maintainable, or more scalable alternatives.",
    DebatePhase.DEVILS_ADVOCATE: "A randomly designated agent must argue against the current design. Prompt: 'Assume this design will fail. Prove why.'",
    DebatePhase.CONSENSUS: "Final convergence. Agents vote on the refined design. Consensus or human decision required.",
}

ASSUMPTION_DIMENSIONS: list[str] = [
    "core_entities",
    "users_and_permissions",
    "data_storage",
    "core_workflow",
    "non_functional",
    "integration_and_boundary",
]

DIMENSION_DESCRIPTIONS: dict[str, str] = {
    "core_entities": "Key objects and concepts in the system",
    "users_and_permissions": "Who uses the system and what permissions model",
    "data_storage": "What data is stored and how",
    "core_workflow": "The 3-5 most common user workflows",
    "non_functional": "Performance, availability, security requirements",
    "integration_and_boundary": "External integrations and explicit out-of-scope items",
}

PERSPECTIVES: list[str] = [
    "cost_efficiency",
    "security_privacy",
    "scalability",
    "developer_experience",
    "operational_stability",
    "user_experience",
    "data_integrity",
    "integration_ecosystem",
]

PERSPECTIVE_DESCRIPTIONS: dict[str, str] = {
    "cost_efficiency": "Focus on minimizing cost: infrastructure, development time, maintenance burden",
    "security_privacy": "Focus on security: attack surface, data protection, compliance, threat modeling",
    "scalability": "Focus on growth: handling 10x load, data volume growth, feature expansion",
    "developer_experience": "Focus on DX: ease of development, debugging, testing, onboarding",
    "operational_stability": "Focus on reliability: fault tolerance, monitoring, rollback, incident response",
    "user_experience": "Focus on UX: responsiveness, accessibility, discoverability, error recovery",
    "data_integrity": "Focus on data: consistency, validation, migration, backup, audit trail",
    "integration_ecosystem": "Focus on integration: APIs, SDKs, third-party compatibility, extensibility",
}

MAX_CLARIFY_ROUNDS = int(os.environ.get("DESIGNDOC_MAX_CLARIFY_ROUNDS", "3"))

CLARITY_DIMENSIONS: list[str] = [
    "core_entities",
    "users_and_permissions",
    "data_storage",
    "core_workflow",
    "non_functional",
    "integration_and_boundary",
    "constraints",
    "acceptance_criteria",
    "tech_stack",
    "scope_boundary",
]

CLARITY_THRESHOLD = float(os.environ.get("DESIGNDOC_CLARITY_THRESHOLD", "0.7"))


class AgentInfo(BaseModel):
    agent_id: str
    name: str
    model: str = ""
    provider: str = ""
    agent_identity: str = ""  # stable identity across reconnects (e.g. "cursor_cli_local_hash")
    client_type: str = ""     # cursor / claude_code / atomcode / generic
    registered_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_active_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_active: bool = True
    current_perspective: str = ""
    runtime_mode: str = "persistent_worker"  # persistent_worker / normal_worker

AGENT_INACTIVE_TIMEOUT_SECONDS = int(os.environ.get("DESIGNDOC_AGENT_TIMEOUT", "300"))


class DecisionOption(BaseModel):
    """决策点的一个选项"""
    option_id: str
    label: str                 # 选项名称，如"PostgreSQL"
    proposed_by: str           # 提出该选项的Agent ID
    reasoning: str = ""        # 理由
    pros: list[str] = []       # 优点
    cons: list[str] = []       # 缺点


class DecisionPoint(BaseModel):
    """一个具体的决策分歧点"""
    decision_id: str
    topic: str                 # 决策主题关键词，如"database"
    description: str           # 背景描述
    options: list[DecisionOption] = []
    constraints: list[str] = []  # 关联约束
    human_choice: str = ""     # 人类最终选择的option_id
    human_custom: str = ""     # 人类自定义输入


class EventType(str, enum.Enum):
    PROPOSAL = "proposal"
    CHALLENGE = "challenge"
    REBUTTAL = "rebuttal"
    REVISION = "revision"
    OPTIMIZATION = "optimization"
    RISK = "risk"
    CONSENSUS_VOTE = "consensus_vote"
    HUMAN_DECISION = "human_decision"
    SYSTEM_EVENT = "system_event"
    QUESTION = "question"
    ASSUMPTION = "assumption"
    ASSUMPTION_SUPPLEMENT = "assumption_supplement"
    REQUIREMENT_REFINE = "requirement_refine"


class ChallengeCategory(str, enum.Enum):
    ARCHITECTURE = "architecture"
    SCALABILITY = "scalability"
    MAINTAINABILITY = "maintainability"
    PERFORMANCE = "performance"
    DEPLOYMENT = "deployment"
    OBSERVABILITY = "observability"
    COST = "cost"
    SECURITY = "security"


class ChallengePriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VoteType(str, enum.Enum):
    AGREE = "agree"
    DISAGREE = "disagree"
    ABSTAIN = "abstain"
    NEEDS_CLARIFICATION = "needs_clarification"


class SessionStatus(str, enum.Enum):
    CREATED = "created"
    CLARIFY_IDENTIFY = "clarify_identify"
    CLARIFY_REFINE = "clarify_refine"
    CLARIFY_REVIEW = "clarify_review"
    CLARIFY_REWRITE = "clarify_rewrite"
    PROPOSAL = "proposal"
    CRITIC = "critic"
    REVISION = "revision"
    OPTIMIZATION = "optimization"
    DEVILS_ADVOCATE = "devils_advocate"
    CONSENSUS = "consensus"
    HUMAN_REVIEW = "human_review"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Event(BaseModel):
    event_id: str
    session_id: str
    round_number: int
    phase: DebatePhase
    event_type: EventType
    source_agent: str
    target_agent: str = ""
    content: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    category: str = ""
    references: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AssumptionAlternative(BaseModel):
    label: str
    description: str = ""


class Assumption(BaseModel):
    assumption_id: str
    session_id: str
    agent_id: str
    dimension: str
    assumption: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    alternatives: list[AssumptionAlternative] = Field(default_factory=list)
    rationale: str = ""
    human_choice: str = ""
    clarify_round: int = 1
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MergedAssumptionGroup(BaseModel):
    dimension: str
    assumptions: list[Assumption] = Field(default_factory=list)
    divergent: bool = False


class RefinedRequirement(BaseModel):
    refine_id: str
    session_id: str
    agent_id: str
    refined_statement: str
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Proposal(BaseModel):
    proposal_id: str
    session_id: str
    agent_id: str
    round_number: int
    perspective: str = ""
    architecture: str = ""
    tech_stack: str = ""
    tradeoffs: str = ""
    risks: str = ""
    assumptions: str = ""
    unknowns: str = ""
    raw_content: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Challenge(BaseModel):
    challenge_id: str
    session_id: str
    agent_id: str
    target_agent_id: str
    target_proposal_id: str
    round_number: int
    risks: list[str] = Field(default_factory=list)
    missing_considerations: list[str] = Field(default_factory=list)
    alternative_proposal: str = ""
    category: ChallengeCategory = ChallengeCategory.ARCHITECTURE
    priority: ChallengePriority = ChallengePriority.MEDIUM
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Revision(BaseModel):
    revision_id: str
    session_id: str
    agent_id: str
    round_number: int
    accepted_feedback: list[str] = Field(default_factory=list)
    rejected_feedback: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    changed_design: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Optimization(BaseModel):
    optimization_id: str
    session_id: str
    agent_id: str
    round_number: int
    description: str = ""
    impact: str = ""
    tradeoff: str = ""
    complexity_change: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DevilsAdvocate(BaseModel):
    da_id: str
    session_id: str
    agent_id: str
    round_number: int
    failure_modes: list[str] = Field(default_factory=list)
    risk_score: float = Field(default=0.5, ge=0.0, le=1.0)
    mitigation: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ConsensusVote(BaseModel):
    vote_id: str
    session_id: str
    agent_id: str
    round_number: int
    vote_type: VoteType
    comment: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class QuestionOption(BaseModel):
    label: str
    description: str = ""


class PendingQuestion(BaseModel):
    question_id: str
    session_id: str
    asked_by: str
    question: str
    options: list[QuestionOption] = Field(default_factory=list)
    resolved: bool = False
    resolution: str = ""
    human_choice: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Requirement(BaseModel):
    requirement_id: str
    session_id: str
    problem_statement: str = ""
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    tech_preferences: list[str] = Field(default_factory=list)
    forbidden_items: list[str] = Field(default_factory=list)
    is_refined: bool = False
    original_statement: str = ""
    clarity_score: float = 0.0
    clarity_dimensions: dict[str, bool] = Field(default_factory=dict)
    skip_clarification: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RequirementDelta(BaseModel):
    delta_id: str
    session_id: str
    parent_delta_id: str | None = None
    problem_statement: str = ""
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    clarity_score: float = 0.0
    clarity_dimensions: dict[str, bool] = Field(default_factory=dict)
    skip_clarification: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HumanVote(BaseModel):
    vote_id: str
    session_id: str
    approver: str
    vote_type: VoteType
    comment: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Session(BaseModel):
    session_id: str
    title: str
    description: str
    status: SessionStatus = SessionStatus.CREATED
    current_phase: DebatePhase = DebatePhase.CREATED
    current_round: int = 1
    min_rounds: int = 4
    max_rounds: int = 8
    clarify_round: int = 1
    agents: list[AgentInfo] = Field(default_factory=list)
    requirement: Requirement | None = None
    assumptions: list[Assumption] = Field(default_factory=list)
    merged_assumptions: list[MergedAssumptionGroup] = Field(default_factory=list)
    clarify_refine_submitted: list[str] = Field(default_factory=list)
    refined_requirements: list[RefinedRequirement] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    proposals: list[Proposal] = Field(default_factory=list)
    challenges: list[Challenge] = Field(default_factory=list)
    revisions: list[Revision] = Field(default_factory=list)
    optimizations: list[Optimization] = Field(default_factory=list)
    devils_advocates: list[DevilsAdvocate] = Field(default_factory=list)
    consensus_votes: list[ConsensusVote] = Field(default_factory=list)
    human_votes: list[HumanVote] = Field(default_factory=list)
    pending_questions: list[PendingQuestion] = Field(default_factory=list)
    decision_points: list[DecisionPoint] = Field(default_factory=list)
    novelty_scores: list[float] = Field(default_factory=list)
    requirement_deltas: list[RequirementDelta] = Field(default_factory=list)
    devils_advocate_agent: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    archived_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
