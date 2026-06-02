// Package mcptools registers all DesignDoc MCP tools and forwards calls to the Python Engine API.
package mcptools

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/fluorine/designdoc-mcp-gateway/internal/proxy"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// objectSchema builds a minimal JSON Schema object descriptor.
func objectSchema(props map[string]any, required []string) map[string]any {
	if required == nil {
		required = []string{}
	}
	return map[string]any{
		"type":       "object",
		"properties": props,
		"required":   required,
	}
}

// RegisterAllTools adds every DesignDoc tool to the MCP server.
func RegisterAllTools(s *mcp.Server, pc *proxy.Client) {
	// -----------------------------------------------------------------------
	// Session management
	// -----------------------------------------------------------------------
	s.AddTool(&mcp.Tool{
		Name:        "create_session",
		Description: "Create a new DesignDoc collaboration session.",
		InputSchema: objectSchema(map[string]any{
			"title":       map[string]any{"type": "string", "description": "Session title"},
			"description": map[string]any{"type": "string", "description": "Session description"},
			"min_rounds":  map[string]any{"type": "integer", "description": "Minimum debate rounds (default 4)"},
			"max_rounds":  map[string]any{"type": "integer", "description": "Maximum debate rounds (default 8)"},
		}, []string{"title"}),
	}, makeProxyHandler(pc, "/api/v1/create_session"))

	s.AddTool(&mcp.Tool{
		Name:        "list_sessions",
		Description: "List all DesignDoc sessions, optionally filtered by status.",
		InputSchema: objectSchema(map[string]any{
			"status": map[string]any{"type": "string", "description": "Filter by status (optional)"},
		}, nil),
	}, makeProxyHandler(pc, "/api/v1/list_sessions"))

	s.AddTool(&mcp.Tool{
		Name:        "get_session",
		Description: "Get full details of a DesignDoc session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/get_session"))

	s.AddTool(&mcp.Tool{
		Name:        "delete_session",
		Description: "Delete a DesignDoc session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/delete_session"))

	s.AddTool(&mcp.Tool{
		Name:        "submit_requirement",
		Description: "Submit the initial problem statement / requirement for a session.",
		InputSchema: objectSchema(map[string]any{
			"session_id":          map[string]any{"type": "string", "description": "Session ID"},
			"requirement":         map[string]any{"type": "string", "description": "Problem statement"},
			"constraints":         map[string]any{"type": "array", "items": map[string]any{"type": "string"}},
			"acceptance_criteria": map[string]any{"type": "array", "items": map[string]any{"type": "string"}},
			"open_questions":      map[string]any{"type": "array", "items": map[string]any{"type": "string"}},
			"tech_preferences":    map[string]any{"type": "array", "items": map[string]any{"type": "string"}},
			"forbidden_items":     map[string]any{"type": "array", "items": map[string]any{"type": "string"}},
		}, []string{"session_id", "requirement"}),
	}, makeProxyHandler(pc, "/api/v1/submit_requirement"))

	// -----------------------------------------------------------------------
	// Agent management
	// -----------------------------------------------------------------------
	s.AddTool(&mcp.Tool{
		Name:        "register_agent",
		Description: "Register an agent to a session. If no session_id is provided and only one active session exists, it is auto-selected.",
		InputSchema: objectSchema(map[string]any{
			"session_id":       map[string]any{"type": "string", "description": "Session ID (optional)"},
			"name":             map[string]any{"type": "string", "description": "Agent display name"},
			"model":            map[string]any{"type": "string", "description": "Model name (optional)"},
			"provider":         map[string]any{"type": "string", "description": "Model provider (optional)"},
			"agent_identity":   map[string]any{"type": "string", "description": "Stable identity for rejoins (optional)"},
			"client_type":      map[string]any{"type": "string", "description": "Client type hint (optional)"},
			"client_info_hint": map[string]any{"type": "string", "description": "MCP handshake clientInfo.name (optional)"},
			"force_mode":       map[string]any{"type": "string", "description": "Force runtime mode: loop / step (optional)"},
		}, []string{"name"}),
	}, makeProxyHandler(pc, "/api/v1/register_agent"))

	s.AddTool(&mcp.Tool{
		Name:        "deregister_agent",
		Description: "Remove an agent from a session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":   map[string]any{"type": "string", "description": "Agent ID"},
		}, []string{"session_id", "agent_id"}),
	}, makeProxyHandler(pc, "/api/v1/deregister_agent"))

	s.AddTool(&mcp.Tool{
		Name:        "heartbeat",
		Description: "Send a heartbeat to keep an agent active.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":   map[string]any{"type": "string", "description": "Agent ID"},
		}, []string{"session_id", "agent_id"}),
	}, makeProxyHandler(pc, "/api/v1/heartbeat"))

	// -----------------------------------------------------------------------
	// Task lifecycle
	// -----------------------------------------------------------------------
	s.AddTool(&mcp.Tool{
		Name:        "wait_for_task",
		Description: "Blocking poll for the next task assigned to this agent. Timeout defaults to 25 seconds.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":   map[string]any{"type": "string", "description": "Agent ID"},
			"timeout":    map[string]any{"type": "integer", "description": "Max seconds to wait (default 25, max 600)"},
		}, []string{"session_id", "agent_id"}),
	}, makeProxyHandler(pc, "/api/v1/wait_for_task"))

	s.AddTool(&mcp.Tool{
		Name:        "submit_result",
		Description: "Submit the result for a completed task.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":   map[string]any{"type": "string", "description": "Agent ID"},
			"task_id":    map[string]any{"type": "string", "description": "Task ID"},
			"result":     map[string]any{"type": "string", "description": "Task result content"},
		}, []string{"session_id", "agent_id", "task_id", "result"}),
	}, makeProxyHandler(pc, "/api/v1/submit_result"))

	// -----------------------------------------------------------------------
	// Phase context
	// -----------------------------------------------------------------------
	s.AddTool(&mcp.Tool{
		Name:        "get_phase_context",
		Description: "Get the current phase instructions and context for an agent.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":   map[string]any{"type": "string", "description": "Agent ID"},
		}, []string{"session_id", "agent_id"}),
	}, makeProxyHandler(pc, "/api/v1/get_phase_context"))

	s.AddTool(&mcp.Tool{
		Name:        "start_clarification",
		Description: "Advance a session to the clarification phase.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/start_clarification"))

	s.AddTool(&mcp.Tool{
		Name:        "start_debate",
		Description: "Advance a session to the debate phase.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/start_debate"))

	// -----------------------------------------------------------------------
	// Submission endpoints
	// -----------------------------------------------------------------------
	s.AddTool(&mcp.Tool{
		Name:        "submit_assumptions",
		Description: "Submit assumptions for the clarification phase.",
		InputSchema: objectSchema(map[string]any{
			"session_id":  map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":    map[string]any{"type": "string", "description": "Agent ID"},
			"assumptions": map[string]any{"type": "string", "description": "Assumptions JSON or text"},
		}, []string{"session_id", "agent_id", "assumptions"}),
	}, makeProxyHandler(pc, "/api/v1/submit_assumptions"))

	s.AddTool(&mcp.Tool{
		Name:        "submit_refined_requirement",
		Description: "Submit a refined requirement during clarification rewrite.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":   map[string]any{"type": "string", "description": "Agent ID"},
			"refined":    map[string]any{"type": "string", "description": "Refined requirement text"},
		}, []string{"session_id", "agent_id", "refined"}),
	}, makeProxyHandler(pc, "/api/v1/submit_refined_requirement"))

	s.AddTool(&mcp.Tool{
		Name:        "submit_proposal",
		Description: "Submit a design proposal during the proposal phase.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":   map[string]any{"type": "string", "description": "Agent ID"},
			"proposal":   map[string]any{"type": "string", "description": "Proposal text"},
		}, []string{"session_id", "agent_id", "proposal"}),
	}, makeProxyHandler(pc, "/api/v1/submit_proposal"))

	s.AddTool(&mcp.Tool{
		Name:        "submit_challenge",
		Description: "Submit a challenge to another agent's proposal.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":   map[string]any{"type": "string", "description": "Agent ID"},
			"challenge":  map[string]any{"type": "string", "description": "Challenge content"},
		}, []string{"session_id", "agent_id", "challenge"}),
	}, makeProxyHandler(pc, "/api/v1/submit_challenge"))

	s.AddTool(&mcp.Tool{
		Name:        "submit_revision",
		Description: "Submit a revised proposal incorporating feedback.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":   map[string]any{"type": "string", "description": "Agent ID"},
			"revision":   map[string]any{"type": "string", "description": "Revision content"},
		}, []string{"session_id", "agent_id", "revision"}),
	}, makeProxyHandler(pc, "/api/v1/submit_revision"))

	s.AddTool(&mcp.Tool{
		Name:        "submit_optimization",
		Description: "Submit an optimization suggestion.",
		InputSchema: objectSchema(map[string]any{
			"session_id":   map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":     map[string]any{"type": "string", "description": "Agent ID"},
			"optimization": map[string]any{"type": "string", "description": "Optimization content"},
		}, []string{"session_id", "agent_id", "optimization"}),
	}, makeProxyHandler(pc, "/api/v1/submit_optimization"))

	s.AddTool(&mcp.Tool{
		Name:        "submit_devils_advocate",
		Description: "Submit devil's advocate arguments against the current design.",
		InputSchema: objectSchema(map[string]any{
			"session_id":      map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":        map[string]any{"type": "string", "description": "Agent ID"},
			"devils_advocate": map[string]any{"type": "string", "description": "Devil's advocate content"},
		}, []string{"session_id", "agent_id", "devils_advocate"}),
	}, makeProxyHandler(pc, "/api/v1/submit_devils_advocate"))

	s.AddTool(&mcp.Tool{
		Name:        "cast_consensus_vote",
		Description: "Cast a consensus vote (agree, disagree, abstain, needs_clarification).",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":   map[string]any{"type": "string", "description": "Agent ID"},
			"vote":       map[string]any{"type": "string", "description": "Vote type: agree | disagree | abstain | needs_clarification"},
		}, []string{"session_id", "agent_id", "vote"}),
	}, makeProxyHandler(pc, "/api/v1/cast_consensus_vote"))

	// -----------------------------------------------------------------------
	// Human review
	// -----------------------------------------------------------------------
	s.AddTool(&mcp.Tool{
		Name:        "request_human_review",
		Description: "Request human review for the current session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/request_human_review"))

	s.AddTool(&mcp.Tool{
		Name:        "human_approve",
		Description: "Human approves the current design.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"approver":   map[string]any{"type": "string", "description": "Human reviewer name"},
			"comment":    map[string]any{"type": "string", "description": "Approval comment (optional)"},
		}, []string{"session_id", "approver"}),
	}, makeProxyHandler(pc, "/api/v1/human_approve"))

	s.AddTool(&mcp.Tool{
		Name:        "human_reject",
		Description: "Human rejects the current design.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"approver":   map[string]any{"type": "string", "description": "Human reviewer name"},
			"reason":     map[string]any{"type": "string", "description": "Rejection reason"},
		}, []string{"session_id", "approver", "reason"}),
	}, makeProxyHandler(pc, "/api/v1/human_reject"))

	s.AddTool(&mcp.Tool{
		Name:        "human_override",
		Description: "Human overrides with a custom decision.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"approver":   map[string]any{"type": "string", "description": "Human reviewer name"},
			"decision":   map[string]any{"type": "string", "description": "Override decision text"},
			"rationale":  map[string]any{"type": "string", "description": "Rationale for override"},
		}, []string{"session_id", "approver", "decision", "rationale"}),
	}, makeProxyHandler(pc, "/api/v1/human_override"))

	// -----------------------------------------------------------------------
	// Utility / query
	// -----------------------------------------------------------------------
	s.AddTool(&mcp.Tool{
		Name:        "get_session_flow",
		Description: "Get the event flow / timeline for a session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/get_session_flow"))

	s.AddTool(&mcp.Tool{
		Name:        "check_stalled",
		Description: "Check whether a session has stalled (agents inactive).",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/check_stalled"))

	s.AddTool(&mcp.Tool{
		Name:        "get_session_diagnostics",
		Description: "Get diagnostic information for a session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/get_session_diagnostics"))

	s.AddTool(&mcp.Tool{
		Name:        "generate_design_document",
		Description: "Generate the final design document for a completed session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/generate_design_document"))

	s.AddTool(&mcp.Tool{
		Name:        "add_requirement_delta",
		Description: "Add a requirement delta (amendment) to a session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":   map[string]any{"type": "string", "description": "Agent ID"},
			"delta":      map[string]any{"type": "string", "description": "Delta content"},
		}, []string{"session_id", "agent_id", "delta"}),
	}, makeProxyHandler(pc, "/api/v1/add_requirement_delta"))

	s.AddTool(&mcp.Tool{
		Name:        "force_skip_clarification",
		Description: "Force skip the clarification phase for a session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/force_skip_clarification"))

	s.AddTool(&mcp.Tool{
		Name:        "pause_session",
		Description: "Pause a session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/pause_session"))

	s.AddTool(&mcp.Tool{
		Name:        "resume_session",
		Description: "Resume a paused session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/resume_session"))

	s.AddTool(&mcp.Tool{
		Name:        "archive_session",
		Description: "Archive a completed session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/archive_session"))

	// Missing tools (added during hybrid refactor audit)
	s.AddTool(&mcp.Tool{
		Name:        "advance_phase",
		Description: "Advance the session to the next phase.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/advance_phase"))

	s.AddTool(&mcp.Tool{
		Name:        "advance_round",
		Description: "Advance the session to the next round.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/advance_round"))

	s.AddTool(&mcp.Tool{
		Name:        "approve_refined_requirement",
		Description: "Approve a refined requirement by its refine_id.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"refine_id":  map[string]any{"type": "string", "description": "Refine ID"},
		}, []string{"session_id", "refine_id"}),
	}, makeProxyHandler(pc, "/api/v1/approve_refined_requirement"))

	s.AddTool(&mcp.Tool{
		Name:        "bulk_resolve_decision_points",
		Description: "Bulk-resolve decision points using a strategy (majority, unanimous, etc.).",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"strategy":   map[string]any{"type": "string", "description": "Resolution strategy (default: majority)"},
			"preview":    map[string]any{"type": "boolean", "description": "Preview only, do not apply (default: false)"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/bulk_resolve_decision_points"))

	s.AddTool(&mcp.Tool{
		Name:        "compare_sessions",
		Description: "Compare two sessions and return differences.",
		InputSchema: objectSchema(map[string]any{
			"session_id_a": map[string]any{"type": "string", "description": "First session ID"},
			"session_id_b": map[string]any{"type": "string", "description": "Second session ID"},
		}, []string{"session_id_a", "session_id_b"}),
	}, makeProxyHandler(pc, "/api/v1/compare_sessions"))

	s.AddTool(&mcp.Tool{
		Name:        "get_merged_assumptions",
		Description: "Get merged assumptions for a session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/get_merged_assumptions"))

	s.AddTool(&mcp.Tool{
		Name:        "get_pending_questions",
		Description: "Get pending questions for a session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/get_pending_questions"))

	s.AddTool(&mcp.Tool{
		Name:        "raise_question",
		Description: "Raise a question during a session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":   map[string]any{"type": "string", "description": "Agent ID"},
			"question":   map[string]any{"type": "string", "description": "Question text"},
			"options":    map[string]any{"type": "array", "description": "Question options (optional)"},
		}, []string{"session_id", "agent_id", "question"}),
	}, makeProxyHandler(pc, "/api/v1/raise_question"))

	s.AddTool(&mcp.Tool{
		Name:        "resolve_decision_point",
		Description: "Resolve a decision point with a choice.",
		InputSchema: objectSchema(map[string]any{
			"session_id":  map[string]any{"type": "string", "description": "Session ID"},
			"decision_id": map[string]any{"type": "string", "description": "Decision ID"},
			"choice":      map[string]any{"type": "string", "description": "Selected option ID (optional)"},
			"custom":      map[string]any{"type": "string", "description": "Custom input (optional)"},
		}, []string{"session_id", "decision_id"}),
	}, makeProxyHandler(pc, "/api/v1/resolve_decision_point"))

	s.AddTool(&mcp.Tool{
		Name:        "resolve_question",
		Description: "Resolve a pending question with a human choice.",
		InputSchema: objectSchema(map[string]any{
			"session_id":   map[string]any{"type": "string", "description": "Session ID"},
			"question_id":  map[string]any{"type": "string", "description": "Question ID"},
			"human_choice": map[string]any{"type": "string", "description": "Selected choice"},
		}, []string{"session_id", "question_id", "human_choice"}),
	}, makeProxyHandler(pc, "/api/v1/resolve_question"))

	s.AddTool(&mcp.Tool{
		Name:        "revert_to_event",
		Description: "Revert session state to a specific event.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"event_id":   map[string]any{"type": "string", "description": "Event ID to revert to"},
		}, []string{"session_id", "event_id"}),
	}, makeProxyHandler(pc, "/api/v1/revert_to_event"))

	s.AddTool(&mcp.Tool{
		Name:        "review_assumptions",
		Description: "Review assumptions with human choices.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"choices":    map[string]any{"type": "array", "description": "List of assumption choices"},
		}, []string{"session_id", "choices"}),
	}, makeProxyHandler(pc, "/api/v1/review_assumptions"))

	s.AddTool(&mcp.Tool{
		Name:        "submit_decision_points",
		Description: "Submit decision points for a session.",
		InputSchema: objectSchema(map[string]any{
			"session_id":      map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":        map[string]any{"type": "string", "description": "Agent ID"},
			"decision_points": map[string]any{"type": "array", "description": "Decision points list"},
		}, []string{"session_id", "agent_id", "decision_points"}),
	}, makeProxyHandler(pc, "/api/v1/submit_decision_points"))

	s.AddTool(&mcp.Tool{
		Name:        "submit_human_vote",
		Description: "Submit a human vote.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
			"approver":   map[string]any{"type": "string", "description": "Human reviewer name"},
			"vote_type":  map[string]any{"type": "string", "description": "Vote type"},
			"comment":    map[string]any{"type": "string", "description": "Comment (optional)"},
		}, []string{"session_id", "approver", "vote_type"}),
	}, makeProxyHandler(pc, "/api/v1/submit_human_vote"))

	s.AddTool(&mcp.Tool{
		Name:        "supplement_assumption_options",
		Description: "Supplement assumption options during clarification.",
		InputSchema: objectSchema(map[string]any{
			"session_id":  map[string]any{"type": "string", "description": "Session ID"},
			"agent_id":    map[string]any{"type": "string", "description": "Agent ID"},
			"supplements": map[string]any{"type": "array", "description": "Supplements list"},
		}, []string{"session_id", "agent_id", "supplements"}),
	}, makeProxyHandler(pc, "/api/v1/supplement_assumption_options"))

	s.AddTool(&mcp.Tool{
		Name:        "generate_design_document_html",
		Description: "Generate an HTML design document for a completed session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/generate_design_document_html"))

	s.AddTool(&mcp.Tool{
		Name:        "generate_design_document_json",
		Description: "Generate a JSON design document for a completed session.",
		InputSchema: objectSchema(map[string]any{
			"session_id": map[string]any{"type": "string", "description": "Session ID"},
		}, []string{"session_id"}),
	}, makeProxyHandler(pc, "/api/v1/generate_design_document_json"))
}

// makeProxyHandler creates a generic MCP ToolHandler that forwards arguments
// to the Python API and returns the JSON response as text.
func makeProxyHandler(pc *proxy.Client, endpoint string) mcp.ToolHandler {
	return func(ctx context.Context, req *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		// req.Params.Arguments is map[string]any.
		result, err := pc.Call(ctx, endpoint, req.Params.Arguments)
		if err != nil {
			return &mcp.CallToolResult{
				IsError: true,
				Content: []mcp.Content{&mcp.TextContent{Text: err.Error()}},
			}, nil
		}
		jsonBytes, err := json.MarshalIndent(result, "", "  ")
		if err != nil {
			return &mcp.CallToolResult{
				IsError: true,
				Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("marshal result: %v", err)}},
			}, nil
		}
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: string(jsonBytes)}},
		}, nil
	}
}
