// Package models defines request/response types mirroring the Python API.
package models

// SessionMinimal is returned by list_sessions.
type SessionMinimal struct {
	SessionID    string `json:"session_id"`
	Title        string `json:"title"`
	Status       string `json:"status"`
	CurrentPhase string `json:"current_phase"`
	CurrentRound int    `json:"current_round"`
	AgentsCount  int    `json:"agents_count"`
}

// AgentInfo mirrors Python AgentInfo.
type AgentInfo struct {
	AgentID           string `json:"agent_id"`
	Name              string `json:"name"`
	Model             string `json:"model"`
	Provider          string `json:"provider"`
	AgentIdentity     string `json:"agent_identity"`
	ClientType        string `json:"client_type"`
	RegisteredAt      string `json:"registered_at"`
	LastActiveAt      string `json:"last_active_at"`
	IsActive          bool   `json:"is_active"`
	CurrentPerspective string `json:"current_perspective"`
	RuntimeMode       string `json:"runtime_mode"`
}

// CreateSessionReq is the body for /api/v1/create_session.
type CreateSessionReq struct {
	Title       string `json:"title"`
	Description string `json:"description"`
	MinRounds   int    `json:"min_rounds"`
	MaxRounds   int    `json:"max_rounds"`
}

// ListSessionsReq is the body for /api/v1/list_sessions.
type ListSessionsReq struct {
	Status string `json:"status,omitempty"`
}

// SessionIDReq is a generic request containing only session_id.
type SessionIDReq struct {
	SessionID string `json:"session_id"`
}

// AgentSessionReq is a generic request containing session_id and agent_id.
type AgentSessionReq struct {
	SessionID string `json:"session_id"`
	AgentID   string `json:"agent_id"`
}

// RegisterAgentReq is the body for /api/v1/register_agent.
type RegisterAgentReq struct {
	SessionID      string `json:"session_id,omitempty"`
	Name           string `json:"name,omitempty"`
	Model          string `json:"model,omitempty"`
	Provider       string `json:"provider,omitempty"`
	AgentIdentity  string `json:"agent_identity,omitempty"`
	ClientType     string `json:"client_type,omitempty"`
	ClientInfoHint string `json:"client_info_hint,omitempty"`
	ForceMode      string `json:"force_mode,omitempty"`
}

// DeregisterAgentReq is the body for /api/v1/deregister_agent.
type DeregisterAgentReq struct {
	SessionID string `json:"session_id"`
	AgentID   string `json:"agent_id"`
}

// HeartbeatReq is the body for /api/v1/heartbeat.
type HeartbeatReq struct {
	SessionID string `json:"session_id"`
	AgentID   string `json:"agent_id"`
}

// WaitForTaskReq is the body for /api/v1/wait_for_task.
type WaitForTaskReq struct {
	SessionID string `json:"session_id"`
	AgentID   string `json:"agent_id"`
	Timeout   int    `json:"timeout,omitempty"`
}

// SubmitResultReq is the body for /api/v1/submit_result.
type SubmitResultReq struct {
	SessionID string `json:"session_id"`
	AgentID   string `json:"agent_id"`
	TaskID    string `json:"task_id"`
	Result    string `json:"result"`
}

// GetPhaseContextReq is the body for /api/v1/get_phase_context.
type GetPhaseContextReq struct {
	SessionID string `json:"session_id"`
	AgentID   string `json:"agent_id"`
}

// SubmitRequirementReq is the body for /api/v1/submit_requirement.
type SubmitRequirementReq struct {
	SessionID          string   `json:"session_id"`
	Requirement        string   `json:"requirement"`
	Constraints        []string `json:"constraints,omitempty"`
	AcceptanceCriteria []string `json:"acceptance_criteria,omitempty"`
	OpenQuestions      []string `json:"open_questions,omitempty"`
	TechPreferences    []string `json:"tech_preferences,omitempty"`
	ForbiddenItems     []string `json:"forbidden_items,omitempty"`
}

// SubmitAssumptionsReq is the body for /api/v1/submit_assumptions.
type SubmitAssumptionsReq struct {
	SessionID   string `json:"session_id"`
	AgentID     string `json:"agent_id"`
	Assumptions string `json:"assumptions"`
}

// SubmitRefinedRequirementReq is the body for /api/v1/submit_refined_requirement.
type SubmitRefinedRequirementReq struct {
	SessionID string `json:"session_id"`
	AgentID   string `json:"agent_id"`
	Refined   string `json:"refined"`
}

// SubmitProposalReq is the body for /api/v1/submit_proposal.
type SubmitProposalReq struct {
	SessionID string `json:"session_id"`
	AgentID   string `json:"agent_id"`
	Proposal  string `json:"proposal"`
}

// SubmitChallengeReq is the body for /api/v1/submit_challenge.
type SubmitChallengeReq struct {
	SessionID string `json:"session_id"`
	AgentID   string `json:"agent_id"`
	Challenge string `json:"challenge"`
}

// SubmitRevisionReq is the body for /api/v1/submit_revision.
type SubmitRevisionReq struct {
	SessionID string `json:"session_id"`
	AgentID   string `json:"agent_id"`
	Revision  string `json:"revision"`
}

// SubmitOptimizationReq is the body for /api/v1/submit_optimization.
type SubmitOptimizationReq struct {
	SessionID     string `json:"session_id"`
	AgentID       string `json:"agent_id"`
	Optimization  string `json:"optimization"`
}

// SubmitDevilsAdvocateReq is the body for /api/v1/submit_devils_advocate.
type SubmitDevilsAdvocateReq struct {
	SessionID      string `json:"session_id"`
	AgentID        string `json:"agent_id"`
	DevilsAdvocate string `json:"devils_advocate"`
}

// CastConsensusVoteReq is the body for /api/v1/cast_consensus_vote.
type CastConsensusVoteReq struct {
	SessionID string `json:"session_id"`
	AgentID   string `json:"agent_id"`
	Vote      string `json:"vote"`
}

// HumanApproveReq is the body for /api/v1/human_approve.
type HumanApproveReq struct {
	SessionID string `json:"session_id"`
	Approver  string `json:"approver"`
	Comment   string `json:"comment,omitempty"`
}

// HumanRejectReq is the body for /api/v1/human_reject.
type HumanRejectReq struct {
	SessionID string `json:"session_id"`
	Approver  string `json:"approver"`
	Reason    string `json:"reason"`
}

// HumanOverrideReq is the body for /api/v1/human_override.
type HumanOverrideReq struct {
	SessionID string `json:"session_id"`
	Approver  string `json:"approver"`
	Decision  string `json:"decision"`
	Rationale string `json:"rationale"`
}

// AddRequirementDeltaReq is the body for /api/v1/add_requirement_delta.
type AddRequirementDeltaReq struct {
	SessionID string `json:"session_id"`
	AgentID   string `json:"agent_id"`
	Delta     string `json:"delta"`
}
