# DesignDoc MCP 技术规格文档

> 本文档是项目实现的唯一权威参考。仅凭本文档即可100%重建整个项目。

---

## 项目进度

### 阶段一：核心框架与基础功能 [已完成]

| 任务 | 状态 | 预计完成 | 实际完成 |
|------|------|---------|---------|
| 项目骨架搭建（pyproject.toml + 目录结构） | ✅ 已完成 | 2026-05-15 | 2026-05-15 |
| 数据模型定义（models.py） | ✅ 已完成 | 2026-05-15 | 2026-05-15 |
| 核心业务逻辑（engine.py — CollaborationEngine） | ✅ 已完成 | 2026-05-16 | 2026-05-16 |
| 数据持久化（store.py — SessionStore + 文件锁） | ✅ 已完成 | 2026-05-16 | 2026-05-16 |
| MCP服务器（server.py — FastMCP工具定义） | ✅ 已完成 | 2026-05-16 | 2026-05-16 |
| Web UI + REST API（web.py + index.html） | ✅ 已完成 | 2026-05-17 | 2026-05-17 |
| 文档生成（document.py — 4层输出） | ✅ 已完成 | 2026-05-17 | 2026-05-17 |

### 阶段二：稳定性修复与安全加固 [已完成]

| 任务 | 状态 | 预计完成 | 实际完成 |
|------|------|---------|---------|
| 文件锁机制修复（O_CREAT + O_EXCL 原子创建） | ✅ 已完成 | 2026-05-18 | 2026-05-18 |
| Web API参数传递修复 | ✅ 已完成 | 2026-05-18 | 2026-05-18 |
| API Token认证机制 | ✅ 已完成 | 2026-05-18 | 2026-05-18 |
| 共识死锁修复（ABSTAIN处理 + 部分共识） | ✅ 已完成 | 2026-05-18 | 2026-05-18 |
| 全局单例去重（web.py委托server.py） | ✅ 已完成 | 2026-05-18 | 2026-05-18 |
| register_agent阶段限制 | ✅ 已完成 | 2026-05-18 | 2026-05-18 |
| human_reject重置到PROPOSAL | ✅ 已完成 | 2026-05-18 | 2026-05-18 |
| EventBus线程安全 | ✅ 已完成 | 2026-05-18 | 2026-05-18 |
| get_session mtime缓存优化 | ✅ 已完成 | 2026-05-18 | 2026-05-18 |

### 阶段三：配置外部化与代码质量 [已完成]

| 任务 | 状态 | 预计完成 | 实际完成 |
|------|------|---------|---------|
| 清晰度评估配置外部化（clarity_config.py） | ✅ 已完成 | 2026-05-19 | 2026-05-19 |
| 魔法数字替换为命名常量 | ✅ 已完成 | 2026-05-19 | 2026-05-19 |
| 配置验证机制（validate_config） | ✅ 已完成 | 2026-05-19 | 2026-05-19 |
| 版本号统一（pyproject.toml vs server.py） | ✅ 已完成 | 2026-05-20 | 2026-05-20 |
| Docker/start.sh传输协议更新（SSE→HTTP） | ✅ 已完成 | 2026-05-20 | 2026-05-19 |
| .trae/mcp.json配置更新 | ✅ 已完成 | 2026-05-20 | 2026-05-19 |
| configs/目录创建与参考配置 | ✅ 已完成 | 2026-05-20 | 2026-05-19 |
| SQLite存储后端（sqlite_store.py） | ✅ 已完成 | 2026-05-19 | 2026-05-19 |
| Blocking-pull协议（wait_for_task/submit_result） | ✅ 已完成 | 2026-05-19 | 2026-05-19 |
| Persistent Agent Runtime 架构（stable identity + auto rejoin） | ✅ 已完成 | 2026-05-20 | 2026-05-20 |

### 阶段四：健壮性提升 [已完成]

| 任务 | 状态 | 预计完成 | 实际完成 |
|------|------|---------|---------|
| Session默认状态修正（NOT_STARTED阶段） | ✅ 已完成 | 2026-05-22 | 2026-05-20 |
| submit_assumptions多轮澄清修复 | ✅ 已完成 | 2026-05-22 | 2026-05-20 |
| submit_challenge目标验证 | ✅ 已完成 | 2026-05-22 | 2026-05-20 |
| _save更新mtime缓存 | ✅ 已完成 | 2026-05-22 | 2026-05-20 |
| 数值字段范围校验（priority枚举化） | ✅ 已完成 | 2026-05-22 | 2026-05-20 |
| 文档生成空架构占位提示 | ✅ 已完成 | 2026-05-22 | 2026-05-19 |
| generate_design_document状态检查 | ✅ 已完成 | 2026-05-22 | 2026-05-26 |
| CLARIFY_REWRITE自动推进逻辑修正 | ✅ 已完成 | 2026-05-22 | 2026-05-16 |

### 阶段五：功能扩展 [部分完成]

| 任务 | 状态 | 预计完成 | 实际完成 |
|------|------|---------|---------|
| deregister_agent MCP工具 | ✅ 已完成 | — | 2026-05-20 |
| delete_session MCP工具 | ✅ 已完成 | — | 2026-05-20 |
| list_sessions分页支持 | ✅ 已完成 | — | 2026-05-20 |
| Session暂停/恢复 | ✅ 已完成 | — | 2026-05-20 |
| 单Agent自审模式 | ✅ 已完成 | — | 2026-05-20 |
| 按分歧点决策（DecisionPoint） | ✅ 已完成 | — | 2026-05-20 |
| 操作回滚/撤销 | 📋 未开始 | — | — |

图例：✅ 已完成 / ⏳ 进行中 / 📋 未开始

---

## 一、项目概览

DesignDoc MCP 是一个MCP驱动的多智能体设计文档协作系统。多个AI智能体通过MCP协议（Streamable HTTP模式）连接到同一个服务器实例，围绕设计需求进行4阶段澄清和6阶段结构化辩论，最终输出4层结构化文档。

### 核心设计原则

1. **假设驱动的需求澄清**：模糊需求先通过4阶段澄清流程精化
2. **结构化辩论替代自由讨论**：6阶段流程强制深度思考，禁止"礼貌性同意"
3. **随机视角替代固定角色**：每轮随机分配思考视角，避免角色逃避
4. **人类只做决策，不控流程**：阶段自动推进，人类仅在决策点介入
5. **单一共享工作空间**：所有Agent连接同一个MCP服务器，共享会话状态
6. **事件溯源**：所有操作记录为事件，完整追溯讨论过程

---

## 二、项目结构

```
designdoc-mcp/
├── pyproject.toml                          # 项目配置、依赖、构建
├── Dockerfile                              # Docker容器化
├── docker-compose.yml                      # Docker编排
├── start.ps1                               # Windows启动脚本
├── configs/
│   └── claude_desktop_config.json          # MCP客户端配置示例
├── docs/
│   ├── specification.md                  # 本文档（技术规格）
│   ├── design-v1.md                      # 原始设计文档
│   ├── decision-points.md                # 按分歧点决策功能规划
│   ├── issues.md                         # 问题跟踪与实现规划
│   └── restructure.md                    # 架构重构方案
├── src/
│   └── designdoc_mcp/
│       ├── __init__.py                     # 包初始化
│       ├── models.py                       # 数据模型、枚举、常量
│       ├── engine.py                       # 核心业务逻辑（CollaborationEngine）
│       ├── server.py                       # MCP服务器（FastMCP工具定义 + main入口）
│       ├── store.py                        # 数据持久化（SessionStore）
│       ├── clarity_config.py               # 清晰度评估配置（维度关键词 + 评分常量）
│       ├── sqlite_store.py                 # SQLite存储后端（StorageBackend + SQLiteBackend）
│       ├── events.py                       # 事件总线（EventBus）
│       ├── web.py                          # Web UI + REST API（FastAPI）
│       ├── document.py                     # 文档生成（4层输出）
│       └── static/
│           └── index.html                  # Web UI前端（Alpine.js + Tailwind CSS）
```

---

## 三、技术栈与依赖

### 运行时依赖

| 包 | 版本约束 | 用途 |
|---|---------|------|
| `fastmcp` | >=2.0 | MCP服务器框架 |
| `fastapi` | >=0.110 | Web UI + REST API |
| `uvicorn` | >=0.29 | ASGI服务器 |
| `pydantic` | >=2.0 | 数据模型与校验 |
| `pydantic-settings` | >=2.0 | 配置管理 |
| `pywin32` | >=306 (仅Windows) | Windows平台支持 |

### 开发依赖

| 包 | 版本约束 | 用途 |
|---|---------|------|
| `pytest` | >=8.0 | 测试框架 |
| `pytest-asyncio` | >=0.23 | 异步测试支持 |
| `ruff` | >=0.4 | 代码格式化与lint |

### 构建配置

- **构建系统**: hatchling
- **Python版本**: >=3.10
- **入口点**: `designdoc-mcp = designdoc_mcp.server:main`
- **Ruff配置**: line-length=120, target-version=py310, select=["E","F","I","N","W"]
- **pytest配置**: asyncio_mode="auto"

### 前端技术

- **Alpine.js** — 响应式UI框架（CDN引入，零构建步骤）
- **Tailwind CSS** — 样式框架（CDN引入，零构建步骤）
- **Font Awesome** — 图标库（CDN引入）
- **Web Audio API** — 浏览器原生声音提醒

---

## 四、数据模型（models.py）

### 4.1 枚举类型

#### DebatePhase — 辩论阶段

```python
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
```

阶段顺序常量：
```python
CLARIFY_PHASES = [CLARIFY_IDENTIFY, CLARIFY_REFINE, CLARIFY_REVIEW, CLARIFY_REWRITE]
DEBATE_PHASES = [PROPOSAL, CRITIC, REVISION, OPTIMIZATION, DEVILS_ADVOCATE, CONSENSUS]
PHASE_ORDER = [CREATED] + CLARIFY_PHASES + DEBATE_PHASES
```

#### SessionStatus — 会话状态

```python
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
```

#### EventType — 事件类型

```python
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
```

#### ChallengeCategory — 挑战分类

```python
class ChallengeCategory(str, enum.Enum):
    ARCHITECTURE = "architecture"
    SCALABILITY = "scalability"
    MAINTAINABILITY = "maintainability"
    PERFORMANCE = "performance"
    DEPLOYMENT = "deployment"
    OBSERVABILITY = "observability"
    COST = "cost"
    SECURITY = "security"
```

#### ChallengePriority — 挑战优先级

```python
class ChallengePriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
```

#### VoteType — 投票类型

```python
class VoteType(str, enum.Enum):
    AGREE = "agree"
    DISAGREE = "disagree"
    ABSTAIN = "abstain"
    NEEDS_CLARIFICATION = "needs_clarification"
```

### 4.2 Pydantic模型

#### AgentInfo

```python
class AgentInfo(BaseModel):
    agent_id: str                                    # 格式: name__model_slug 或 name
    name: str                                        # 显示名称
    model: str = ""                                  # LLM模型标识
    provider: str = ""                               # 模型提供商
    agent_identity: str = ""                         # stable identity across reconnects
    client_type: str = ""                            # cursor / claude_code / atomcode / generic
    runtime_mode: str = "persistent_worker"          # persistent_worker / normal_worker
    registered_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 UTC
    last_active_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 UTC，提交/心跳时更新
    is_active: bool = True                           # 超时后标记为False
    current_perspective: str = ""                    # 当前分配的视角
```

**agent_id生成规则**：
- `base_id = name.lower().replace(" ", "_")`
- 若提供model: `model_slug = model.lower().replace("-", "_").replace(".", "_").replace(" ", "_")`，`agent_id = f"{base_id}__{model_slug}"`
- 否则: `agent_id = base_id`

#### Event

```python
class Event(BaseModel):
    event_id: str                                    # uuid4 hex[:10]
    session_id: str
    round_number: int
    phase: DebatePhase
    event_type: EventType
    source_agent: str                                # "system" 表示系统事件
    target_agent: str = ""                           # 空字符串表示广播
    content: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    category: str = ""
    references: list[str] = []
    metadata: dict[str, Any] = {}
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 UTC
```

#### AssumptionAlternative

```python
class AssumptionAlternative(BaseModel):
    label: str
    description: str = ""
```

#### Assumption

```python
class Assumption(BaseModel):
    assumption_id: str                               # uuid4 hex[:8]
    session_id: str
    agent_id: str
    dimension: str                                   # ASSUMPTION_DIMENSIONS之一
    assumption: str                                  # 假设内容
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    alternatives: list[AssumptionAlternative] = []   # 自动追加"Other"选项
    rationale: str = ""
    clarify_round: int = 1                           # 用于区分不同澄清轮次的假设提交
    human_choice: str = ""                           # 人类审核后的选择
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 UTC
```

#### MergedAssumptionGroup

```python
class MergedAssumptionGroup(BaseModel):
    dimension: str
    assumptions: list[Assumption] = []
    divergent: bool = False                          # 多个Agent意见不一致
```

#### RefinedRequirement

```python
class RefinedRequirement(BaseModel):
    refine_id: str                                   # uuid4 hex[:8]
    session_id: str
    agent_id: str
    refined_statement: str
    constraints: list[str] = []
    acceptance_criteria: list[str] = []
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 UTC
```

#### Proposal

```python
class Proposal(BaseModel):
    proposal_id: str                                 # uuid4 hex[:8]
    session_id: str
    agent_id: str
    round_number: int
    perspective: str = ""                            # 分配的视角
    architecture: str = ""
    tech_stack: str = ""
    tradeoffs: str = ""
    risks: str = ""
    assumptions: str = ""
    unknowns: str = ""
    raw_content: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 UTC
```

#### Challenge

```python
class Challenge(BaseModel):
    challenge_id: str                                # uuid4 hex[:8]
    session_id: str
    agent_id: str
    target_agent_id: str
    target_proposal_id: str
    round_number: int
    risks: list[str] = []
    missing_considerations: list[str] = []
    alternative_proposal: str = ""
    category: ChallengeCategory = ChallengeCategory.ARCHITECTURE
    priority: ChallengePriority = ChallengePriority.MEDIUM
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 UTC
```

#### Revision

```python
class Revision(BaseModel):
    revision_id: str                                 # uuid4 hex[:8]
    session_id: str
    agent_id: str
    round_number: int
    accepted_feedback: list[str] = []
    rejected_feedback: list[str] = []
    rejection_reasons: list[str] = []
    changed_design: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 UTC
```

#### Optimization

```python
class Optimization(BaseModel):
    optimization_id: str                             # uuid4 hex[:8]
    session_id: str
    agent_id: str
    round_number: int
    description: str = ""
    impact: str = ""
    tradeoff: str = ""
    complexity_change: str = ""                      # increased/decreased/neutral
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 UTC
```

#### DevilsAdvocate

```python
class DevilsAdvocate(BaseModel):
    da_id: str                                       # uuid4 hex[:8]
    session_id: str
    agent_id: str
    round_number: int
    failure_modes: list[str] = []
    risk_score: float = Field(default=0.5, ge=0.0, le=1.0)
    mitigation: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 UTC
```

#### ConsensusVote

```python
class ConsensusVote(BaseModel):
    vote_id: str                                     # uuid4 hex[:8]
    session_id: str
    agent_id: str
    round_number: int
    vote_type: VoteType
    comment: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 UTC
```

#### DecisionOption

```python
class DecisionOption(BaseModel):
    """决策点的一个选项"""
    option_id: str
    label: str                 # 选项名称，如"PostgreSQL"
    proposed_by: str           # 提出该选项的Agent ID
    reasoning: str = ""        # 理由
    pros: list[str] = []       # 优点
    cons: list[str] = []       # 缺点
```

#### DecisionPoint

```python
class DecisionPoint(BaseModel):
    """一个具体的决策分歧点"""
    decision_id: str
    topic: str                 # 决策主题关键词
    description: str           # 背景描述
    options: list[DecisionOption] = []
    constraints: list[str] = []
    human_choice: str = ""
    human_custom: str = ""
```

#### QuestionOption

```python
class QuestionOption(BaseModel):
    label: str
    description: str = ""
```

#### PendingQuestion

```python
class PendingQuestion(BaseModel):
    question_id: str                                 # uuid4 hex[:8]
    session_id: str
    asked_by: str
    question: str
    options: list[QuestionOption] = []               # 自动追加"Other"选项
    resolved: bool = False
    resolution: str = ""
    human_choice: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 UTC
```

#### Requirement

```python
class Requirement(BaseModel):
    requirement_id: str                              # uuid4 hex[:8]
    session_id: str
    problem_statement: str = ""
    constraints: list[str] = []
    acceptance_criteria: list[str] = []
    open_questions: list[str] = []
    tech_preferences: list[str] = []
    forbidden_items: list[str] = []
    is_refined: bool = False                         # 澄清后重写为True
    original_statement: str = ""                     # 保留原始模糊需求
    clarity_score: float = 0.0                       # 0.0~1.0
    clarity_dimensions: dict[str, bool] = {}         # 各维度覆盖情况
    skip_clarification: bool = False                 # clarity_score >= 0.7时为True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 UTC
```

#### Session

```python
class Session(BaseModel):
    session_id: str                                  # uuid4 hex[:12]
    title: str
    description: str
    status: SessionStatus = SessionStatus.CREATED
    current_phase: DebatePhase = DebatePhase.CREATED
    current_round: int = 1
    min_rounds: int = 4
    max_rounds: int = 8
    clarify_round: int = 1
    agents: list[AgentInfo] = []
    requirement: Requirement | None = None
    assumptions: list[Assumption] = []
    merged_assumptions: list[MergedAssumptionGroup] = []
    clarify_refine_submitted: list[str] = []           # CLARIFY_REFINE阶段已提交补充的agent_id列表
    refined_requirements: list[RefinedRequirement] = []
    events: list[Event] = []
    proposals: list[Proposal] = []
    challenges: list[Challenge] = []
    revisions: list[Revision] = []
    optimizations: list[Optimization] = []
    devils_advocates: list[DevilsAdvocate] = []
    consensus_votes: list[ConsensusVote] = []
    pending_questions: list[PendingQuestion] = []
    decision_points: list[DecisionPoint] = []          # 按分歧点提交的决策
    novelty_scores: list[float] = []
    devils_advocate_agent: str = ""                  # 被指定为魔鬼代言人的agent_id
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 UTC
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 UTC
    completed_at: str | None = None
    archived_at: str | None = None
    metadata: dict[str, Any] = {}
```

### 4.3 常量

#### 阶段描述（PHASE_DESCRIPTIONS）

| 阶段 | 描述 |
|------|------|
| CREATED | Session created, waiting for requirement submission and agent registration. |
| CLARIFY_IDENTIFY | Each agent independently identifies assumptions in the fuzzy requirement. Do NOT read other agents' assumptions. Produce a structured assumption document organized by dimension. Each assumption must include alternatives for human to choose from. |
| CLARIFY_REFINE | System has merged all assumptions. Agents can now supplement alternatives to existing assumptions, but cannot remove or challenge assumptions raised by others. Focus on adding missing options. |
| CLARIFY_REVIEW | Human reviews the merged assumption document. For each assumption, human can accept the default or choose an alternative. Divergent assumptions (agents disagree) must be resolved. |
| CLARIFY_REWRITE | Based on human choices, agents propose a refined requirement document. The refined requirement replaces the original fuzzy statement. |
| PROPOSAL | Each agent independently proposes a solution from their assigned perspective. Agents MUST NOT read other agents' proposals to avoid anchoring bias. |
| CRITIC | Agents challenge each other's proposals. Each agent MUST: (1) identify at least 3 risks, 2 missing considerations, and 1 alternative; (2) submit decision_points for key divergences (e.g., database choice, deployment strategy) where agents propose different solutions. Vague agreement like 'I agree' or 'looks good' is FORBIDDEN. |
| REVISION | Agents revise their proposals by incorporating valid feedback. Must explicitly state accepted/rejected feedback with reasons. Polite acknowledgment without design changes is FORBIDDEN. |
| OPTIMIZATION | Agents propose optimizations: simpler, more stable, cheaper, more maintainable, or more scalable alternatives. |
| DEVILS_ADVOCATE | A randomly designated agent must argue against the current design. Prompt: 'Assume this design will fail. Prove why.' |
| CONSENSUS | Final convergence. Agents vote on the refined design. Consensus or human decision required. |

#### 假设维度（ASSUMPTION_DIMENSIONS）

| 维度 | 描述 |
|------|------|
| `core_entities` | Key objects and concepts in the system |
| `users_and_permissions` | Who uses the system and what permissions model |
| `data_storage` | What data is stored and how |
| `core_workflow` | The 3-5 most common user workflows |
| `non_functional` | Performance, availability, security requirements |
| `integration_and_boundary` | External integrations and explicit out-of-scope items |

#### 清晰度评估维度（CLARITY_DIMENSIONS）及关键词

| 维度 | 检测关键词 |
|------|-----------|
| `core_entities` | entity, entities, model, object, component, module, layer, 架构, 模型, 实体, 组件, 模块, 层 |
| `users_and_permissions` | user, role, permission, auth, access, sensitivity, visibility, 用户, 权限, 角色, 访问, 敏感 |
| `data_storage` | storage, database, store, persist, sqlite, jsonl, file, index, 存储, 数据库, 持久, 索引 |
| `core_workflow` | workflow, pipeline, process, flow, ingest, extract, retrieve, query, 流程, 管道, 工作流, 检索 |
| `non_functional` | performance, scalability, security, latency, throughput, local, offline, 性能, 安全, 扩展, 本地 |
| `integration_and_boundary` | integration, api, external, boundary, scope, not include, not do, 集成, 边界, 范围, 不含 |
| `constraints` | constraint, must, shall, required, never, forbidden, 约束, 必须, 禁止, 不得 |
| `acceptance_criteria` | criteria, acceptance, verify, test, validate, 验收, 标准, 验证, 测试 |
| `tech_stack` | python, typescript, react, sqlite, docker, framework, library, 技术栈, 框架, 依赖 |
| `scope_boundary` | scope, not include, not do, out of scope, mvp, phase, 范围, 不含, 不做, 阶段 |

#### 视角列表（PERSPECTIVES）及描述

| 视角 | 描述 |
|------|------|
| `cost_efficiency` | Focus on minimizing cost: infrastructure, development time, maintenance burden |
| `security_privacy` | Focus on security: attack surface, data protection, compliance, threat modeling |
| `scalability` | Focus on growth: handling 10x load, data volume growth, feature expansion |
| `developer_experience` | Focus on DX: ease of development, debugging, testing, onboarding |
| `operational_stability` | Focus on reliability: fault tolerance, monitoring, rollback, incident response |
| `user_experience` | Focus on UX: responsiveness, accessibility, discoverability, error recovery |
| `data_integrity` | Focus on data: consistency, validation, migration, backup, audit trail |
| `integration_ecosystem` | Focus on integration: APIs, SDKs, third-party compatibility, extensibility |

#### 其他常量

| 常量 | 值 | 说明 |
|------|---|------|
| `MAX_CLARIFY_ROUNDS` | 3 | 澄清阶段最大轮次 |
| `CLARITY_THRESHOLD` | 0.7 | 清晰度达标阈值 |
| `AGENT_INACTIVE_TIMEOUT_SECONDS` | 300 | Agent不活跃超时（秒） |
| `NOVELTY_THRESHOLD` | 0.15 | 新颖度阈值（engine.py） |

#### 维度描述（DIMENSION_DESCRIPTIONS）

```python
DIMENSION_DESCRIPTIONS: dict[str, str] = {
    "core_entities": "Focus on entities: objects, data models, relationships, attributes",
    "users_and_permissions": "Focus on users: roles, permissions, access control, authentication",
    "workflow_and_business_logic": "Focus on workflow: business rules, processes, state machines",
    "non_functional_requirements": "Focus on NFRs: performance, security, reliability, scalability",
    "integration_and_apis": "Focus on integration: APIs, third-party services, data exchange",
    "tech_stack": "Focus on tech stack: languages, frameworks, databases, infrastructure",
    "scope_boundary": "Focus on scope: MVP definition, phased delivery, out-of-scope items",
}
```

---

## 五、核心业务逻辑（engine.py）

### 5.1 CollaborationEngine 类

构造函数接收 `SessionStore` 实例，所有操作通过 `self.store` 持久化。

### 5.2 需求清晰度评估算法（_evaluate_clarity）

```
输入: Requirement对象
处理:
  1. 合并所有文本字段: problem_statement + constraints + acceptance_criteria + tech_preferences + forbidden_items
  2. 对每个CLARITY_DIMENSIONS维度，检查是否有任何关键词出现在合并文本中
  3. 计算覆盖维度数 / 总维度数 = base_score
  4. length_bonus = min(0.15, len(problem_statement) / 10000)
  5. field_bonus = 0.05 * (has_constraints + has_criteria + has_forbidden)  (每个非空字段+0.05)
  6. clarity_score = min(1.0, base_score + length_bonus + field_bonus)
  7. skip_clarification = (clarity_score >= 0.7)
输出: 修改req.clarity_score, req.clarity_dimensions, req.skip_clarification
```

### 5.3 假设合并算法（_merge_assumptions）

```
1. 按dimension分组所有assumptions
2. 对每个维度内的assumptions进行相似度分组:
   a. 取assumption文本的前60字符（小写去空格）作为key
   b. 使用_assumptions_similar()比较key与已有分组key
   c. 相似度 > 0.5 的归入同一组，否则新建分组
3. 对每个组合并:
   a. 取组内第一个assumption作为primary
   b. 合并所有alternatives，按label去重（不区分大小写）
   c. 确保包含"Other"选项
   d. divergent = (组内>1个agent) AND (组内assumption文本不完全相同)
   e. confidence取组内最大值
4. 生成MergedAssumptionGroup列表
```

**相似度算法（_assumptions_similar）**：
- 将字符串按空格分词为集合
- Jaccard系数 = 交集大小 / 最大集合大小
- 阈值 > 0.5 判定为相似

### 5.4 阶段完成检查（_check_phase_completion）

**核心原则**：阶段推进必须满足两个前提条件：
1. **所有agent已完成当前阶段提交**（活跃agent数或总agent数）
2. **无人类介入需求**（HUMAN_REVIEW状态下禁止自动推进）

| 阶段 | 完成条件 | 推进行为 |
|------|---------|---------|
| CLARIFY_IDENTIFY | 提交假设的agent数 >= 应提交agent数 | → CLARIFY_REFINE（触发_merge_assumptions） |
| CLARIFY_REFINE | 提交补充的agent数 >= 应提交agent数（追踪`clarify_refine_submitted`列表） | → CLARIFY_REVIEW |
| CLARIFY_REVIEW | 不自动推进（等待人类审核假设） | 人类调用`review_assumptions`后推进 |
| CLARIFY_REWRITE | 提交精炼需求的agent数 >= 应提交agent数 | → PROPOSAL（需人类`approve_refined_requirement`后） |
| PROPOSAL | 当前轮次提交数 >= agent数 | → CRITIC |
| CRITIC | 当前轮次提交数 >= agent数 | → REVISION |
| REVISION | 当前轮次提交数 >= agent数 | → OPTIMIZATION |
| OPTIMIZATION | 当前轮次提交数 >= agent数 | → DEVILS_ADVOCATE（随机指定DA agent） |
| DEVILS_ADVOCATE | 至少1人提交 | → CONSENSUS |
| CONSENSUS | 所有agent投票后执行_check_consensus | 见下文 |

**守卫条件**：
- `session.status == HUMAN_REVIEW` 时，`_check_phase_completion` 直接返回，不执行任何推进
- `advance_phase` 手动推进在 `HUMAN_REVIEW` 状态下抛出 `ValueError`
- `force_active_only`参数：当为True时，使用活跃agent数代替总agent数作为完成阈值（用于agent断线场景）

### 5.5 共识检查算法（_check_consensus）

```
统计当前轮次各投票类型数量: agrees, disagrees, needs_clarification, abstains

判断逻辑（按顺序）:
1. agrees == 总agent数 → COMPLETED（全票通过）
2. agrees > 0 AND (disagrees + needs_clarification) == 0 → COMPLETED（同意+弃权）
3. disagrees >= 2 OR needs_clarification >= 2 → HUMAN_REVIEW（严重分歧）
4. (disagrees + needs_clarification) >= 1 AND agrees >= 1 → HUMAN_REVIEW（部分共识）

注意: 若投票数 < 总agent数，直接返回（等待更多投票）
```

### 5.6 自动推进副作用（_auto_advance）

推进到下一阶段时的额外操作：
- **→ CLARIFY_REFINE**: 执行 `_merge_assumptions(session)`
- **→ DEVILS_ADVOCATE**: `session.devils_advocate_agent = random.choice([a.agent_id for a in session.agents])`
- **→ PROPOSAL**: 执行 `_assign_perspectives(session)`
- **每次推进后**: 执行 `_push_tasks_for_phase(session)` 为活跃agent创建新阶段任务

### 5.7 视角分配算法（_assign_perspectives）

```python
available = list(PERSPECTIVES)  # 8个视角
random.shuffle(available)
for i, agent in enumerate(session.agents):
    agent.current_perspective = available[i % len(available)]
```

### 5.8 Agent注册限制（register_agent）

- **禁止注册的阶段**: CRITIC, REVISION, OPTIMIZATION, DEVILS_ADVOCATE, CONSENSUS
- **禁止注册的状态**: COMPLETED, ARCHIVED
- **重复注册**: 若agent_id已存在，保留`current_perspective`，替换其余字段
- **返回值**:
  - `rejoined: bool` — 是否为自动 rejoin
  - `runtime_mode: str` — persistent_worker / normal_worker
  - `phase: str` — 当前阶段
  - `pending_task: dict | None` — 待处理任务

### 5.9 提交验证规则

#### submit_challenge 验证

| 验证项 | 条件 | 错误行为 |
|--------|------|----------|
| 阶段检查 | 当前阶段必须为 CRITIC | ValueError |
| 提交者验证 | agent_id 必须是已注册Agent | ValueError |
| 目标Agent存在 | **验证** target_agent_id 必须是已注册Agent | ValueError |
| 目标提案存在 | **验证** target_proposal_id 必须在当前轮次提案中 | ValueError |
| 自我挑战 | **多Agent禁止** target_agent_id == agent_id；**单Agent允许**（active_count == 1时允许自审） | ValueError（多Agent时） |
| 重复提交 | **不检查** 同一agent可多次提交challenge | 允许 |

#### submit_assumptions 重复提交检查

| 验证项 | 条件 | 错误行为 |
|--------|------|----------|
| 阶段检查 | 当前阶段必须为 CLARIFY_IDENTIFY | ValueError |
| 重复提交 | 同一 agent_id 在同一 clarify_round 已有假设记录（`a.agent_id == agent_id and a.clarify_round == session.clarify_round`） | ValueError |
| "Other"选项 | alternatives 中无 "Other" 项 | 自动追加 `AssumptionAlternative(label="Other", description="Custom input")` |

### 5.10 Agent活跃度管理

**_touch_agent**: 每次提交操作时调用，更新 `last_active_at` 和 `is_active = True`

**_mark_inactive_agents**: 遍历所有活跃agent，若 `(now - last_active_at) > 300秒`，标记 `is_active = False`

**check_stalled**:
1. 标记不活跃agent
2. 若当前阶段需要全员提交且有agent变为不活跃:
   - 活跃agent >= 1: `can_auto_advance = True`，触发 `_check_phase_completion(force_active_only=True)`
   - 活跃agent == 0: `stalled = True`
3. CONSENSUS阶段且stalled: → HUMAN_REVIEW
4. CONSENSUS阶段且活跃agent < 2: → HUMAN_REVIEW

### 5.11 轮次推进（advance_round）

- `current_round += 1`
- `current_phase = CRITIC`，`status = CRITIC`（新轮次从CRITIC开始，保留已有提案直接进入批评）
- `devils_advocate_agent = ""`（清空DA指定）
- 若 `current_round >= max_rounds`: → HUMAN_REVIEW

### 5.12 人类决策处理

**human_approve**: 
- 要求 `status == HUMAN_REVIEW`
- 设置 `status = COMPLETED`，记录 `completed_at`
- 记录 `metadata["human_approver"]` 和 `metadata["human_approval_comment"]`

**human_reject**:
- 要求 `status == HUMAN_REVIEW`
- `current_round += 1`
- `current_phase = PROPOSAL`，`status = PROPOSAL`
- 重新分配视角 `_assign_perspectives(session)`

**human_override**:
- 不要求特定状态（但禁止 ARCHIVED 状态）
- `if session.status == SessionStatus.ARCHIVED: raise ValueError(...)`
- `status = COMPLETED`，记录 `completed_at`
- 记录 `metadata["human_override"] = {decision, rationale, approver}`

### 5.13 Auto Rejoin

register_agent 支持通过 agent_identity 自动 rejoin：
- 如果 agent_identity 匹配已有 agent → 恢复该 agent（更新 metadata，保留 perspective），返回 rejoined=true
- 如果 agent_identity 不匹配 → 创建新 agent，返回 rejoined=false
- Rejoin 不受 late_registration_phases 限制（已有 agent 可随时重新连接）
- Rejoin 时保留 current_perspective，更新 is_active=True 和 last_active_at

### 5.14 需求增量处理（add_requirement_delta）

根据当前阶段和delta清晰度，返回不同的action：

| 当前阶段 | delta清晰 | 组合清晰 | action | 说明 |
|---------|----------|---------|--------|------|
| 辩论阶段 | 任意 | 任意 | `delta_appended_to_debate` | 追加到当前辩论 |
| 澄清阶段 | 清晰 | — | `delta_clear_no_clarification_needed` | 继续当前澄清 |
| 澄清阶段 | 模糊 | — | `delta_needs_clarification` | 同时澄清delta |
| 其他(CREATED) | — | 清晰 | `auto_skip_clarification` | 可直接跳到辩论 |
| 其他(CREATED) | — | 模糊 | `needs_clarification` | 需要澄清 |

### 5.15 get_phase_context 响应结构

| 阶段 | 返回字段 |
|------|---------|
| CLARIFY_IDENTIFY | `dimensions`, `your_assumptions`, `submitted_agents`, `total_agents` |
| CLARIFY_REFINE | `merged_assumptions`, `your_supplements` |
| CLARIFY_REVIEW | `merged_assumptions`, `divergent_assumptions` |
| CLARIFY_REWRITE | `merged_assumptions`, `human_choices`, `your_refined_requirement` |
| PROPOSAL | `perspective`, `perspective_description`, `other_proposals_visible=False`, `your_existing_proposal` |
| CRITIC | `proposals`（当前轮次）, `your_challenges` |
| REVISION | `challenges_against_you`, `your_revisions` |
| OPTIMIZATION | `revisions`（当前轮次）, `your_optimizations` |
| DEVILS_ADVOCATE | `is_devils_advocate`, `current_design_summary`, `your_da_submission` |
| CONSENSUS | `design_summary`, `your_vote`, `votes_cast`, `total_agents` |

所有阶段都包含: `phase`, `round`, `clarify_round`, `instruction`, `requirement`

### 5.16 get_session_flow 响应结构

```json
{
  "session_id": "...",
  "title": "...",
  "status": "...",
  "current_phase": "...",
  "current_round": 1,
  "clarify_round": 1,
  "requirement_refined": false,
  "assumption_decisions": [{"dimension": "...", "assumption": "...", "human_choice": "...", "divergent": false}],
  "key_decisions": [{"type": "human_decision|phase_transition", "phase": "...", "content": "...", "timestamp": "..."}],
  "round_summaries": [{"round": 1, "proposals": 2, "challenges": 2, "revisions": 2, "consensus_votes": {"agree": 1, "disagree": 1, "needs_clarification": 0}}],
  "total_events": 42,
  "unresolved_questions": 1
}
```

---

## 六、数据持久化（store.py）

### 6.1 SessionStore 类

#### 构造函数

```python
def __init__(self, data_dir: str | None = None):
    # data_dir默认: $DESIGNDOC_DATA_DIR 或 ~/.designdoc_mcp
    self.data_dir = Path(data_dir)
    self.sessions_dir = data_dir / "sessions"
    self.docs_dir = data_dir / "docs"
    self.history_dir = data_dir / "history"
    self.archive_dir = data_dir / "archive"
    self.requirements_dir = data_dir / "requirements"
    self._sessions: dict[str, Session] = {}        # 内存缓存
    self._mtimes: dict[str, float] = {}             # 文件修改时间缓存
```

#### 目录结构

```
data_dir/
├── sessions/              # {session_id}.json — 会话状态
├── docs/                  # {safe_title}.md — 生成的设计文档
├── history/               # {session_id}_history.json — 完整讨论历史
├── requirements/          # {session_id}_requirement.md — 需求文件
└── archive/
    └── {session_id}/      # 归档目录
        ├── session.json
        ├── *.md           # 文档
        ├── history.json
        └── requirement.md
```

#### 文件锁机制（_acquire_lock / _release_lock）

```
锁文件路径: sessions/{session_id}.lock
获取锁:
  1. 使用 os.open(path, O_CREAT | O_EXCL | O_WRONLY) 原子性创建
  2. 写入当前进程PID
  3. 若FileExistsError: 检查锁文件年龄，超过timeout则强制删除重试
  4. 重试间隔: 0.05秒
  5. 超时: 5秒后抛出TimeoutError
释放锁: 删除锁文件
```

#### 原子写入（_save）

```
1. 更新 session.updated_at
2. 创建临时文件: tempfile.mkstemp(dir=sessions_dir, suffix=".tmp", prefix=session_id)
3. 写入JSON: session.model_dump_json(indent=2)
4. 原子重命名: shutil.move(tmp_path, session_path)
5. 异常时清理临时文件
6. 更新内存缓存（_sessions），并更新mtime缓存（_mtimes）
   注意: 后续_reload_session会因mtime变更而重新读取，但内存中已有最新数据
```

#### mtime缓存优化（_reload_session）

```
1. 获取文件st_mtime
2. 若缓存mtime >= 当前mtime: 跳过加载（文件未变更）
3. 否则: 重新读取、解析、验证、更新缓存
```

#### 归档流程（archive_session）

```
1. 要求 status == COMPLETED
2. 创建 archive/{session_id}/ 目录
3. 复制: session.json, 相关文档, history.json, requirement.md
4. 更新: status = ARCHIVED, archived_at = now
5. 清理工作数据: 删除 requirements/, docs/, history/ 中的对应文件
```

#### 文件命名规则

- 会话文件: `{session_id}.json`
- 需求文件: `{session_id}_requirement.md`
- 历史文件: `{session_id}_history.json`
- 文档文件: `{safe_title}.md`，其中 `safe_title = 非字母数字字符替换为"_"`

---

## 七、事件总线（events.py）

### EventBus 单例

```python
class EventBus:
    _subscribers: dict[str, list[asyncio.Queue[str]]]  # session_id → 队列列表
    _lock: threading.Lock                                # 线程安全保护

event_bus = EventBus()  # 全局单例
```

### 方法

| 方法 | 说明 |
|------|------|
| `subscribe(session_id)` | 创建 `asyncio.Queue(maxsize=1000)` 并加入订阅列表 |
| `unsubscribe(session_id, queue)` | 从订阅列表移除队列，列表为空时删除key |
| `emit(session_id, event_type, data)` | 广播事件到所有订阅者 |

### emit 流程

```
1. 构建payload: json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
2. 加锁复制订阅者列表
3. 对每个队列: q.put_nowait(payload)
4. QueueFull的队列标记为dead
5. 加锁移除dead队列
```

### _add_event 发射的 SSE 数据结构

engine.py 的 `_add_event` 方法通过 `event_bus.emit()` 发射的数据是 Event 模型的子集：

```json
{
  "type": "proposal",
  "data": {
    "event_id": "abc1234567",
    "session_id": "...",
    "round": 1,
    "phase": "proposal",
    "source_agent": "agent_a",
    "target_agent": "",
    "content": "Submitted proposal..."
  }
}
```

注意：SSE payload 不包含 Event 模型的 `confidence`、`category`、`references`、`metadata`、`created_at` 字段。

---

## 八、MCP服务器（server.py）

### 8.1 服务器配置

```python
mcp = FastMCP(name="DesignDoc MCP", version="0.3.0")
```

### 8.2 全局单例模式

```python
_store: SessionStore | None = None
_engine: CollaborationEngine | None = None

def _get_store() -> SessionStore:    # 懒初始化
def _get_engine() -> CollaborationEngine:  # 懒初始化，依赖_get_store()
```

### 8.3 MCP工具完整签名

#### 会话管理

| 工具 | 签名 |
|------|------|
| `create_session` | `(title: str, description: str, min_rounds: int = 4, max_rounds: int = 8) → dict` |
| `list_sessions` | `(status: str \| None = None) → list[dict]` |
| `get_session` | `(session_id: str) → dict` |
| `get_session_flow` | `(session_id: str) → dict` |
| `archive_session` | `(session_id: str) → dict` |

#### 需求与注册

| 工具 | 签名 |
|------|------|
| `submit_requirement` | `(session_id, problem_statement, constraints=None, acceptance_criteria=None, open_questions=None, tech_preferences=None, forbidden_items=None) → dict` |
| `register_agent` | `(session_id="", name="", model="", provider="", agent_identity="", client_type="") → dict` |
| `add_requirement_delta` | `(session_id, delta_statement, constraints=None, acceptance_criteria=None) → dict` |
| `force_skip_clarification` | `(session_id) → dict` |

> register_agent 的 session_id 为空时自动选择唯一活跃会话。agent_identity 为 stable identity，跨 reconnect 保持稳定。如果匹配已有 agent，自动 rejoin（不创建新 agent）。client_type 用于 runtime capability detection。

#### 澄清阶段

| 工具 | 签名 |
|------|------|
| `start_clarification` | `(session_id) → dict` |
| `submit_assumptions` | `(session_id, agent_id, assumptions: list[dict]) → list[dict]` |
| `supplement_assumption_options` | `(session_id, agent_id, supplements: list[dict]) → dict` |
| `get_merged_assumptions` | `(session_id) → list[dict]` |
| `review_assumptions` | `(session_id, choices: list[dict]) → dict` |
| `submit_refined_requirement` | `(session_id, agent_id, refined_statement, constraints=None, acceptance_criteria=None) → dict` |
| `approve_refined_requirement` | `(session_id, refine_id) → dict` |

#### 辩论阶段

| 工具 | 签名 |
|------|------|
| `start_debate` | `(session_id) → dict` |
| `get_phase_context` | `(session_id, agent_id) → dict` |
| `submit_proposal` | `(session_id, agent_id, architecture, tech_stack="", tradeoffs="", risks="", assumptions="", unknowns="", raw_content="") → dict` |
| `submit_challenge` | `(session_id, agent_id, target_agent_id, target_proposal_id, risks: list[str], missing_considerations: list[str], alternative_proposal="", category="architecture", priority="medium", confidence=0.5) → dict` |
| `submit_revision` | `(session_id, agent_id, accepted_feedback: list[str], rejected_feedback: list[str], rejection_reasons: list[str], changed_design) → dict` |
| `submit_optimization` | `(session_id, agent_id, description, impact="", tradeoff="", complexity_change="") → dict` |
| `submit_devils_advocate` | `(session_id, agent_id, failure_modes: list[str], risk_score=0.5, mitigation="") → dict` |
| `cast_consensus_vote` | `(session_id, agent_id, vote_type: str, comment="") → dict` |

#### 调度与监控

| 工具 | 签名 |
|------|------|
| `advance_phase` | `(session_id) → dict` |
| `advance_round` | `(session_id) → dict` |
| `heartbeat` | `(session_id, agent_id) → dict` |
| `check_stalled` | `(session_id) → dict` |

#### 任务分发

| 工具 | 签名 |
|------|------|
| `wait_for_task` | `(session_id, agent_id, timeout=300) → dict` |
| `submit_result` | `(session_id, agent_id, task_id, result) → dict` |

#### 决策与生命周期

| 工具 | 签名 |
|------|------|
| `submit_decision_points` | `(session_id, agent_id, decision_points) → dict` |
| `resolve_decision_point` | `(session_id, decision_id, choice="", custom="") → dict` |
| `deregister_agent` | `(session_id, agent_id) → dict` |
| `delete_session` | `(session_id) → dict` |

#### 问题与决策

| 工具 | 签名 |
|------|------|
| `raise_question` | `(session_id, agent_id, question, options=None) → dict` |
| `resolve_question` | `(session_id, question_id, choice) → dict` |
| `get_pending_questions` | `(session_id) → list[dict]` |
| `request_human_review` | `(session_id, reason) → dict` |
| `human_approve` | `(session_id, approver, comment="") → dict` |
| `human_reject` | `(session_id, approver, reason) → dict` |
| `human_override` | `(session_id, approver, decision, rationale) → dict` |

#### 文档生成

| 工具 | 签名 |
|------|------|
| `generate_design_document` | `(session_id) → str` |

### 8.4 MCP资源

| URI | 说明 | 输出格式 |
|-----|------|---------|
| `designdoc://sessions` | 列出所有会话 | 每行: `- {session_id}: {title} [{status}] Phase: {phase} Round: {round}`；空时: "No sessions found." |
| `designdoc://session/{session_id}` | 获取会话设计文档 | `generate_design_document(session)` 的完整Markdown；不存在时: "Session '{session_id}' not found." |
| `designdoc://active-session` | 获取当前活跃会话信息 | JSON格式会话摘要；无活跃会话时返回提示信息 |

### 8.5 main() 入口函数

```
命令行参数:
  --transport: stdio | sse | http | streamable-http (默认: $DESIGNDOC_TRANSPORT 或 stdio)
  --host: 监听地址 (默认: $DESIGNDOC_HOST 或 0.0.0.0)
  --port: 监听端口 (默认: $DESIGNDOC_PORT 或 8765)
  --no-web: 禁用Web UI (默认: $DESIGNDOC_NO_WEB == "1")

启动逻辑:
  stdio模式: mcp.run(transport="stdio")
  其他模式:
    mcp_app = mcp.http_app(transport=args.transport)
    → sse: 创建路由 /sse (GET) + /messages (POST)
    → http/streamable-http: 创建路由 /mcp
    if not no_web:
      mcp_app.routes.append(Mount("/", app=web_app))  # Web UI作为catch-all
    app = mcp_app
    if DESIGNDOC_LOG_DIR:
      添加文件日志处理器 (designdoc_mcp.log)
    uvicorn.run(app, host=host, port=port)

MCP端点URL:
  sse模式: http://localhost:8765/sse
  http模式: http://localhost:8765/mcp
  Web UI: http://localhost:8765/
```

### 8.6 MCP Prompts

| 名称 | 描述 | 用途 |
|------|------|------|
| `designdoc_guide` | 协作协议指南 | 为Agent提供完整的协作流程说明 |

#### designdoc_guide

返回 DesignDoc 协作的完整指南文本，包括：
- 注册流程（/register → register_agent → heartbeat → get_phase_context）
- 各阶段提交规则（Critic阶段需同时提交challenges和decision_points）
- Runtime Loop（wait_for_task → process → submit_result 循环）
- Rejoin机制（相同agent_identity自动恢复）
- 禁止行为列表（禁止用户确认、禁止聊天模式等）

---

## 九、Web UI + REST API（web.py）

### 9.1 FastAPI应用

```python
web_app = FastAPI(title="DesignDoc MCP - Web UI")
```

### 9.2 认证机制

```python
async def _verify_token(request: Request) -> None:
    token = os.environ.get("DESIGNDOC_API_TOKEN", "")
    if not token: return  # 未设置token时不启用认证
    # 从Authorization头获取: "Bearer <token>"
    # 或从查询参数获取: ?token=<token>
    # 使用 secrets.compare_digest() 进行时间安全比较
    # 不匹配: HTTP 401
```

### 9.3 API端点

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/` | GET | 否 | Web UI HTML页面 |
| `/api/sessions` | GET | 否 | 列出所有会话（支持limit/offset/status分页参数） |
| `/api/sessions/{id}` | GET | 否 | 会话详情（_serialize_session格式） |
| `/api/sessions/{id}/events` | GET(SSE) | 否 | 实时事件流（30秒keepalive） |
| `/api/sessions/{id}/document` | GET | 否 | 设计文档内容 |
| `/api/sessions/create` | POST | 是 | 创建新会话 |
| `/api/sessions/{id}/submit-requirement` | POST | 是 | 提交需求 |
| `/api/sessions/{id}/upload-requirement` | POST | 是 | 上传需求文件 |
| `/api/sessions/{id}/add-requirement-delta` | POST | 是 | 追加需求增量 |
| `/api/register-agent` | POST | 是 | 自动注册Agent（自动发现会话） |
| `/api/sessions/{id}/register-agent` | POST | 是 | 注册Agent到指定会话 |
| `/api/sessions/{id}/start-clarification` | POST | 是 | 启动澄清阶段 |
| `/api/sessions/{id}/review-assumptions` | POST | 是 | 人类审核假设 |
| `/api/sessions/{id}/approve-refined-requirement` | POST | 是 | 批准重写需求 |
| `/api/sessions/{id}/resolve-question` | POST | 是 | 解决待决问题 |
| `/api/sessions/{id}/human-decision` | POST | 是 | 人类决策（approve/reject/override） |
| `/api/sessions/{id}/resolve-decision-point` | POST | 是 | 按分歧点决策 |
| `/api/sessions/{id}/force-skip-clarification` | POST | 是 | 强制跳过澄清 |
| `/api/sessions/{id}/check-stalled` | POST | 是 | 检测停滞 |
| `/api/sessions/{id}/heartbeat/{agent_id}` | POST | 是 | 发送心跳 |
| `/api/sessions/{id}/generate-document` | POST | 是 | 生成设计文档 |
| `/api/sessions/{id}/archive` | POST | 是 | 归档会话 |
| `/api/sessions/{id}/pause` | POST | 是 | 暂停会话 |
| `/api/sessions/{id}/resume` | POST | 是 | 恢复会话 |
| `/api/sessions/{id}` | DELETE | 是 | 删除已归档会话 |

### 9.4 human-decision API 请求体

```
POST /api/sessions/{session_id}/human-decision
Content-Type: application/json

action: "approve" | "reject" | "override"
reason: string (approve时作为comment, reject时作为reason)
decision: string (仅override使用, 为空时fallback到action值)
rationale: string (仅override使用, 为空时fallback到reason值)
```

| action | 调用 | 说明 |
|--------|------|------|
| `approve` | `human_approve(session_id, "human", comment=reason)` | approver硬编码为"human" |
| `reject` | `human_reject(session_id, "human", reason=reason)` | approver硬编码为"human" |
| `override` | `human_override(session_id, "human", decision=decision\|action, rationale=rationale\|reason)` | decision/rationale有fallback |

### 9.5 _serialize_session 响应结构

```json
{
  "session_id": "...",
  "title": "...",
  "description": "...",
  "status": "...",
  "phase": "...",
  "round": 1,
  "min_rounds": 4,
  "max_rounds": 8,
  "agents": [{"agent_id": "...", "name": "...", "model": "...", "provider": "...", "agent_identity": "...", "client_type": "...", "runtime_mode": "...", "perspective": "...", "is_active": true, "last_active_at": "...", "last_active_ago": "5m ago"}],
  "requirement": {"problem_statement": "...", "constraints": [], "acceptance_criteria": [], "clarity_score": 0.0, "skip_clarification": false, "is_refined": false},
  "assumptions": [{"assumption_id": "...", "agent_id": "...", "dimension": "...", "assumption": "...", "confidence": 0.5, "alternatives": [...], "human_choice": "", "clarify_round": 1}],
  "merged_assumptions": [{"dimension": "...", "divergent": false, "assumptions": [{"assumption_id": "...", "agent_id": "...", "assumption": "...", "confidence": 0.5, "alternatives": [...], "human_choice": ""}]}],
  "refined_requirements": [{"refine_id": "...", "agent_id": "...", "refined_statement": "...(截断200字)"}],
  "proposals": [{"proposal_id": "...", "agent_id": "...", "architecture": "...", "tech_stack": "...", "tradeoffs": "...", "risks": "...", "perspective": "...", "round": 1}],
  "challenges": [{"challenge_id": "...", "agent_id": "...", "target_agent_id": "...", "target_proposal_id": "...", "risks": [...], "missing_considerations": [...], "category": "architecture", "priority": "medium", "round": 1}],
  "revisions": [{"revision_id": "...", "agent_id": "...", "accepted_feedback": [...], "rejected_feedback": [...], "changed_design": "...", "round": 1}],
  "optimizations": [{"optimization_id": "...", "agent_id": "...", "description": "...", "impact": "...", "tradeoff": "...", "round": 1}],
  "devils_advocates": [{"da_id": "...", "agent_id": "...", "failure_modes": [...], "risk_score": 0.5, "mitigation": "...", "round": 1}],
  "votes": [{"agent_id": "...", "vote_type": "...", "comment": "...", "round": 1}],
  "pending_questions": [{"question_id": "...", "asked_by": "...", "question": "...", "options": [...]}],
  "decision_points": [{"decision_id": "...", "topic": "...", "description": "...", "options": [{"option_id": "...", "label": "...", "proposed_by": "...", "reasoning": "...", "pros": [...], "cons": [...]}], "constraints": [...], "human_choice": "", "human_custom": ""}],
  "events": [...],  // 最近100条
  "phase_progress": [{"key": "clarify_identify", "label": "Identify", "status": "done|active|pending"}],
  "needs_human": false,
  "human_actions": [],  // 可能值: review_debate, review_assumptions, approve_refined_requirement, resolve_questions
  "human_review_reason": ""
}
```

### 9.6 人类决策检测逻辑

```
needs_human = false
human_actions = []

if status == HUMAN_REVIEW:
    needs_human = true
    human_actions.append("review_debate")

if phase == CLARIFY_REVIEW AND merged_assumptions中存在未审核项:
    needs_human = true
    human_actions.append("review_assumptions")

if phase == CLARIFY_REWRITE AND refined_requirements非空:
    needs_human = true
    human_actions.append("approve_refined_requirement")

if pending_questions非空:
    needs_human = true
    human_actions.append("resolve_questions")
```

### 9.7 SSE事件流

```
GET /api/sessions/{session_id}/events

响应格式: text/event-stream
事件格式: data: {"type": "event_type", "data": {...}}\n\n
保活格式: : keepalive\n\n
超时: 30秒无事件则发送保活
队列: asyncio.Queue(maxsize=1000)
断开: 自动unsubscribe
```

### 9.8 单例委托

web.py 的 `_get_store()` 和 `_get_engine()` 委托给 server.py 的同名函数，确保全局唯一实例：

```python
def _get_store() -> SessionStore:
    from .server import _get_store as _server_get_store
    return _server_get_store()
```

---

## 十、文档生成（document.py）

### 10.1 四层输出

| 函数 | 输出 | 说明 |
|------|------|------|
| `generate_design_document(session)` | str | 设计文档（Markdown） |
| `generate_adr(session)` | str | 架构决策记录 |
| `generate_debate_summary(session)` | str | 辩论摘要 |
| `generate_human_decision_points(session)` | str | 人类决策点 |

`generate_full_output(session)` 返回 `dict[str, str]`，包含以上4个键。

### 10.2 设计文档章节结构

1. **Header**: 标题、生成时间、Session ID、轮次数、参与者
2. **Overview**: 描述、参与Agent表格（名称/模型/提供商/视角）
3. **Requirement**: 原始需求（如有）、精化后需求
4. **Goals & Constraints**: 验收标准、约束、技术偏好、禁止项
5. **Assumption Decisions**: 按维度列出澄清阶段的假设决策
6. **Final Architecture**: 取最新轮次数据。优先显示Revision（`_get_latest_revisions`），其次显示Proposal（`_get_latest_proposals`）。每个条目优先显示 `architecture` 字段，为空时显示 `raw_content`
7. **Technical Decisions**: 技术栈、优化建议
8. **Data Model & API**: 占位文本
9. **Risks & Mitigations**: 合并所有来源的风险（Proposal/Challenge/DA），去重
10. **Implementation Plan**: 占位文本
11. **Acceptance Criteria**: 验收标准清单

### 10.3 ADR章节结构

对每个决策生成：
- Decision
- Alternatives Considered
- Tradeoffs
- Rationale

决策来源：假设决策、Proposal、Optimization

### 10.4 辩论摘要章节结构

1. **Clarification Phase Summary**: 假设数、分歧数、解决数
2. **Major Challenges Raised**: 每个Challenge的详情
3. **Resolved Questions**: 已解决的待决问题
4. **Key Improvements**: Revision和Optimization
5. **Event Timeline**: 最近30条事件表格

### 10.5 人类决策点章节结构

1. **Divergent Assumption Resolutions**: 分歧假设及人类选择
2. **Unresolved Questions**: 未解决的待决问题
3. **Disputed Decisions**: 反对/需澄清的投票
4. **High-Risk Failure Modes**: risk_score >= 0.7的DA分析
5. **Review Required**: HUMAN_REVIEW状态时的可用操作

---

## 十一、Web UI前端（static/index.html）

### 11.1 技术方案

- **Alpine.js** — 响应式数据绑定（CDN引入）
- **Tailwind CSS** — 样式（CDN引入）
- **Font Awesome** — 图标（CDN引入）
- **零构建步骤** — 纯HTML文件，无打包器

### 11.2 三个主题

| 主题 | 风格 | CSS变量 |
|------|------|---------|
| Midnight | 深色IDE风格 | 深色背景、亮色文字 |
| Daylight | 浅色极简风格 | 白色背景、深色文字 |
| Ember | 暖色调专注风格 | 暖色背景、对比文字 |

主题选择保存到 `localStorage`，页面右上角切换。

### 11.3 通知系统

| 类型 | 实现 | 触发条件 |
|------|------|---------|
| 浏览器通知 | `Notification API`（需用户授权） | 人类决策点出现 |
| 声音提醒 | `Web Audio API`（OscillatorNode，880Hz→660Hz→880Hz，0.5秒） | 人类决策点出现 |
| Toast通知 | Alpine.js组件，自动消失 | 状态变更 |
| 模态弹窗 | Alpine.js组件，需手动关闭 | 人类决策操作 |

声音提醒可通过UI开关控制。

### 11.4 页面功能

| 页面 | 功能 |
|------|------|
| Dashboard | 会话列表、状态概览、Agent信息（含模型和活跃状态） |
| Process | 实时协作过程（阶段进度条、提案卡片、共识投票、假设组） |
| Events | SSE实时事件时间线 |
| Decisions | 人类决策界面（假设审核、需求批准、问题解决、辩论审核） |
| Document | 设计文档Markdown预览 |

---

## 十二、部署配置

### 12.1 本地运行

```bash
# 安装依赖
uv sync

# 直接启动
uv run designdoc-mcp --transport http --port 8765

# 或使用启动脚本
.\start.ps1 -Transport http -Port 8765
.\start.ps1 -Transport http -Port 8765 -DataDir "D:\data\designdoc"
.\start.ps1 -Transport http -Port 8765 -ApiToken "your-secret-token"
```

### 12.2 start.ps1 脚本逻辑

```
参数: -Transport (默认http), -Port (默认8765), -DataDir, -ApiToken
步骤:
  1. 检查uv是否安装
  2. uv sync 安装依赖
  3. 设置 DESIGNDOC_DATA_DIR 环境变量（若提供DataDir）
  4. 设置 DESIGNDOC_API_TOKEN 环境变量（若提供ApiToken）
  5. 设置 DESIGNDOC_TRANSPORT 和 DESIGNDOC_PORT
  6. 启动: uv run designdoc-mcp --transport $Transport --port $Port
```

### 12.3 Docker部署

**Dockerfile**:
```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN uv venv /app/.venv && uv pip install --python /app/.venv/bin/python -e .
ENV DESIGNDOC_DATA_DIR=/data
ENV DESIGNDOC_TRANSPORT=http
ENV DESIGNDOC_HOST=0.0.0.0
ENV DESIGNDOC_PORT=8765
ENV PATH="/app/.venv/bin:$PATH"
VOLUME ["/data"]
EXPOSE 8765
ENTRYPOINT ["designdoc-mcp", "--transport", "http", "--host", "0.0.0.0", "--port", "8765"]
```

**docker-compose.yml**:
```yaml
services:
  designdoc-mcp:
    build: .
    container_name: designdoc-mcp
    ports:
      - "8765:8765"
    volumes:
      - designdoc-data:/data
    environment:
      - DESIGNDOC_DATA_DIR=/data
      - DESIGNDOC_TRANSPORT=http
      - DESIGNDOC_HOST=0.0.0.0
      - DESIGNDOC_PORT=8765
    restart: unless-stopped

volumes:
  designdoc-data:
```

### 12.4 MCP客户端配置

#### 支持的传输协议

| 协议 | 端点URL | 说明 |
|------|---------|------|
| **Streamable HTTP** (推荐) | `http://localhost:8765/mcp` | 所有Agent通用，`type: "http"` |
| SSE | `http://localhost:8765/sse` | 旧版协议，部分客户端兼容 |
| stdio | — | 单Agent本地模式，无Web UI，无法多Agent共享 |

#### MCP配置文件位置

| Agent | 配置文件路径 | 说明 |
|-------|-------------|------|
| **Claude Code** | `.mcp.json` | 项目根目录，自动识别 |
| **Cursor** | `.cursor/mcp.json` | 自动识别项目级配置 |
| **Trae** | `.trae/mcp.json` | 自动识别项目级配置 |
| **AtomCode** | `.mcp.json` | 与 Claude Code 共用同一配置 |
| **Claude Desktop** | 系统级配置目录 | macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`，Windows: `%APPDATA%\Claude\claude_desktop_config.json` |

> 项目 `configs/` 目录下保存了各客户端的参考配置：`cursor_mcp_config.json`、`trae_mcp_config.json`、`claude_desktop_config.json`。

#### MCP 客户端官方文档

| 客户端 | 官方文档 | 说明 |
|--------|---------|------|
| **Claude Code** | [通过 MCP 将 Claude Code 连接到工具](https://code.claude.com/docs/zh-CN/mcp) | 支持 stdio / SSE / Streamable HTTP 三种传输；项目级 `.mcp.json` 配置；OAuth 2.0 认证；动态工具更新；自动重连 |
| **Cursor** | [Cursor MCP 文档](https://cursor.com/cn/docs/mcp) | 支持 stdio / SSE / Streamable HTTP；MCP 应用扩展；静态 OAuth 配置；扩展 API 动态注册；配置插值（`${env:NAME}`） |
| **Trae** | [添加 MCP Server](https://docs.trae.cn/ide/add-mcp-servers) | 内置 MCP 市场；手动配置 stdio / HTTP；项目级 `.trae/mcp.json`；超时配置；`${workspaceFolder}` 变量引用 |
| **AtomCode** | [MCP 集成](https://atomcode.atomgit.com/docs/mcp.html) | 兼容 Cursor mcpServers 配置块；`atomcode mcp add` 命令行添加；权限审批机制；`/mcp` 斜杠命令管理 |

#### 推荐配置（Streamable HTTP）

```json
{"mcpServers": {"designdoc": {"type": "http", "url": "http://localhost:8765/mcp"}}}
```

**Claude Desktop / Cursor / Trae / AtomCode**: 均使用上述配置。

### 12.5 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DESIGNDOC_DATA_DIR` | `~/.designdoc_mcp` | 数据存储根目录 |
| `DESIGNDOC_TRANSPORT` | `stdio` | 传输协议 (stdio/sse/http/streamable-http) |
| `DESIGNDOC_HOST` | `0.0.0.0` | SSE/HTTP监听地址 |
| `DESIGNDOC_PORT` | `8765` | SSE/HTTP监听端口 |
| `DESIGNDOC_API_TOKEN` | 空 | API认证Token（空=不启用认证） |
| `DESIGNDOC_NO_WEB` | 空 | 设为`1`禁用Web UI |
| `DESIGNDOC_STORAGE` | `json` | 存储后端类型 (json/sqlite) |
| `DESIGNDOC_LOG_DIR` | 空 | 日志文件目录（空=仅控制台输出，设置后写入 `designdoc_mcp.log`） |

---

## 十三、安全机制

### API Token认证

- 通过 `DESIGNDOC_API_TOKEN` 环境变量配置
- 未设置时：所有API开放访问（本地开发友好）
- 设置后：所有POST写操作端点需要认证
- 认证方式：
  1. `Authorization: Bearer <token>` 请求头
  2. `?token=<token>` 查询参数（SSE端点适用）
- 使用 `secrets.compare_digest()` 进行时间安全比较，防止时序攻击
- GET读操作端点不需要认证

---

## 十四、协作流程（5种场景）

### 场景一：模糊需求（完整4+6流程）

```
1. create_session → Session(CREATED)
2. submit_requirement → clarity_score < 0.7, skip_clarification=False
3. register_agent × 2+
4. start_clarification → CLARIFY_IDENTIFY
   → submit_assumptions (各Agent独立提交，全部完成后) → 自动推进到 CLARIFY_REFINE
   → supplement_assumption_options (各Agent补充，全部完成后) → 自动推进到 CLARIFY_REVIEW
   → review_assumptions (人类决策点1：审核假设) → CLARIFY_REWRITE
   → submit_refined_requirement (各Agent提交，全部完成后) → approve_refined_requirement (人类决策点2：批准需求) → PROPOSAL
5. 6阶段辩论循环
6. generate_design_document → 4层输出
7. archive_session → 归档并清理
```

### 场景二：详细需求（跳过澄清）

```
1. create_session
2. submit_requirement(详细文档) → clarity_score >= 0.7, skip_clarification=True
3. register_agent × 2+
4. start_clarification → 自动跳过，直接进入PROPOSAL（分配视角）
5-7. 同场景一
```

### 场景三：详细文档追加模糊需求

```
1-4. 同场景二，进入辩论
5. add_requirement_delta(delta_statement="模糊需求")
   → delta_clarity < 0.7, combined_clarity >= 0.7
   → action: "delta_appended_to_debate"
   → Agent在辩论中同时考虑新增需求
6-7. 同场景一
```

### 场景四：澄清中追加需求

```
1-4. 同场景一，进入澄清
5. add_requirement_delta(delta_statement="模糊需求")
   → delta_clarity < 0.7
   → action: "delta_needs_clarification"
   → Agent同时提交关于delta的假设
6-7. 继续澄清 → 辩论 → 文档 → 归档
```

### 场景五：强制跳过澄清

```
1-4. 同场景一，进入澄清
5. force_skip_clarification → 直接进入PROPOSAL
6-7. 辩论 → 文档 → 归档
```

---

## 十五、人类介入模型

| 决策点 | 触发条件 | 可用操作 |
|--------|----------|---------|
| 假设审核 | CLARIFY_REVIEW阶段，存在未审核假设 | `review_assumptions` |
| 需求批准 | CLARIFY_REWRITE阶段，Agent提交重写需求 | `approve_refined_requirement` |
| 待决问题 | Agent提出待决问题 | `resolve_question` |
| 共识分歧 | 2+反对/需澄清，或部分共识 | `human_approve` / `human_reject` / `human_override` |
| 最大轮次 | current_round >= max_rounds | 同上 |

**关键设计**：所有问题都提供备选项，人类只需选择而非输入。最后一项总是"Other"供自定义。

---

## 十六、Agent容错机制

### 生存追踪

- `AgentInfo.last_active_at`: 每次提交操作或心跳时更新
- `AgentInfo.is_active`: 默认True，超时后标记为False

### 超时检测

- `AGENT_INACTIVE_TIMEOUT_SECONDS = 300`（5分钟）
- `check_stalled` 工具标记超时agent
- 建议心跳间隔: 60秒

### 多数推进

- 阶段完成由活跃agent的提交数决定
- `force_active_only=True` 时使用活跃agent数作为阈值

### CONSENSUS回退

- 所有agent不活跃: → HUMAN_REVIEW
- 活跃agent < 2: → HUMAN_REVIEW

### 重连恢复

- Agent重新注册时保留 `current_perspective`
- 之前的提交数据仍然保留在Session中
