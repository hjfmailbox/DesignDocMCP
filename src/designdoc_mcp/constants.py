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
# Default blocking duration for wait_for_task (LOOP / persistent_worker mode).
# 建议范围: 20~60s。务必保持 < 已知客户端的单次工具调用硬上限(Kimi/AtomCode = 300s)，
# 否则在这些客户端上单次阻塞会被强制 kill，导致循环静默中断。
# 实时性要求低时可调大以降低请求量；要更稳可保持 25s。可手动修改此值。
WAIT_FOR_TASK_TIMEOUT = 25
WAIT_FOR_TASK_MIN_TIMEOUT = 1
WAIT_FOR_TASK_MAX_TIMEOUT = 600
SSE_KEEPALIVE_SECONDS = 30

# Runtime capability detection (see skills/register/SKILL.md).
# Clients verified to sustain a long autonomous tool-call loop without user
# confirmation, tool-call-count caps, or turn-duration caps → LOOP mode.
# 经压力测试确认支持长时自主循环的客户端 → persistent_worker(LOOP) 模式。
# 不在此集合内的客户端(含空/generic/trae 等) → normal_worker(STEP) 模式 + /resume 手动泵。
KNOWN_PERSISTENT_CLIENTS = frozenset({"cursor", "claude_code", "atomcode", "kimi"})
RUNTIME_MODE_LOOP = "persistent_worker"
RUNTIME_MODE_STEP = "normal_worker"

# Canonical client_type ← keyword matching, applied to (in priority order) the
# agent-provided client_type, the MCP handshake clientInfo.name/title, and the
# agent display name. First keyword hit wins, so order matters (most specific
# first). Lets us identify the client even when the agent self-reports nothing
# (e.g. Cursor sends clientInfo.name="Cursor"/"cursor-vscode"; Claude Code sends
# "claude-code"). Kimi's handshake is generic ("mcp"), but its agent name
# contains "Kimi", so name-based matching covers it.
CLIENT_TYPE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("claude_code", ("claude code", "claude-code", "claudecode")),
    ("atomcode", ("atomcode", "atom code", "atom-code")),
    ("cursor", ("cursor",)),
    ("kimi", ("kimi",)),
    ("trae", ("trae",)),  # recognized, but NOT in KNOWN_PERSISTENT_CLIENTS → STEP
)

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
