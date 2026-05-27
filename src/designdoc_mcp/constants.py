"""Runtime constants for DesignDoc MCP.

Centralizes hardcoded literals from engine, web, and server layers.
Event content and replay-sensitive strings are intentionally kept in-place.
"""

# Session defaults
DEFAULT_MIN_ROUNDS = 4
DEFAULT_MAX_ROUNDS = 8

# Consensus thresholds
CONSENSUS_SEVERE_DISAGREEMENT_THRESHOLD = 2
CONSENSUS_PARTIAL_AGREEMENT_MIN = 1

# Assumption / clarity thresholds
NOVELTY_THRESHOLD = 0.15
ASSUMPTION_SIMILARITY_THRESHOLD = 0.5

# Timeouts (seconds)
TASK_POLL_TIMEOUT = 0.1
WAIT_FOR_TASK_TIMEOUT = 300
WAIT_FOR_TASK_MIN_TIMEOUT = 1
WAIT_FOR_TASK_MAX_TIMEOUT = 600
SSE_KEEPALIVE_SECONDS = 30

# Challenge / vote defaults
DEFAULT_CONFIDENCE = 0.5
DEFAULT_CHALLENGE_CATEGORY = "architecture"
DEFAULT_CHALLENGE_PRIORITY = "medium"
DEFAULT_VOTE_TYPE = "agree"

# Requirement delta actions
ACTION_DELTA_APPENDED_TO_DEBATE = "delta_appended_to_debate"
ACTION_DELTA_CLEAR_NO_CLARIFICATION_NEEDED = "delta_clear_no_clarification_needed"
ACTION_DELTA_NEEDS_CLARIFICATION = "delta_needs_clarification"
ACTION_AUTO_SKIP_CLARIFICATION = "auto_skip_clarification"
ACTION_NEEDS_CLARIFICATION = "needs_clarification"

# Agent registration actions
ACTION_REGISTERED = "registered"
ACTION_REJOINED = "rejoined"
