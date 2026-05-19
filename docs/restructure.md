下面是重新优化后的“系统级架构重构 + 实现提示词”。

这个版本已经包含：

* SQLite-first
* MCP Server = Agent Runtime Backend
* 单 Session 模型
* `/register` 生命周期
* blocking pull loop
* SKILL.md 协议化
* runtime bias
* 非 websocket
* 非聊天室
* workflow-driven debate
* persistent participant model

可直接交给外部 agent（Claude Code / Cursor CLI / Gemini CLI 等）。

---

你是 Principal Systems Architect / Multi-Agent Runtime Architect。

你的任务是：

> 对一个 MCP 驱动的多 Agent 设计评审系统进行架构重构，并给出可落地实现方案。

注意：

这不是普通聊天系统。

也不是实时协同编辑系统。

这是：

> “有限轮次、多 Agent、自动推进的设计评审系统（Design Review Swarm）”

目标：

通过多个 Agent 的结构化讨论，提升需求文档或设计文档质量。

==================================================

# 一、核心目标

==================================================

系统目标：

* 多 Agent 独立 proposal
* critic round
* revision
* optimization
* devil advocate
* consensus

最终输出：

高质量、可直接进入开发的设计文档。

系统重点：

> 提升设计质量，而不是实现自治 AI。

==================================================

# 二、核心架构约束（必须严格遵守）

==================================================

这是系统的硬约束。

你必须围绕这些约束设计。

---

## 1. MCP Server = Agent Runtime Backend

---

MCP Server 不是普通 tool provider。

它必须承担：

* orchestrator
* workflow engine
* state machine
* task scheduler
* context provider
* runtime backend
* skill distributor
* session lifecycle manager

即：

> MCP Server 是整个系统的大脑。

---

## 2. 禁止 WebSocket-first 架构

---

不要把系统设计成：

Agent A ↔ Agent B

或：

实时聊天室。

这是错误方向。

系统不是 chat system。

系统是：

> workflow-driven debate system。

禁止：

* websocket-first
* direct agent messaging
* shared realtime memory
* peer-to-peer communication

---

## 3. Pull-based Task Model（最重要）

---

Agent 不监听 push 消息。

必须：

> Agent 主动 pull task。

模型：

register
→ wait_for_task()
→ process
→ submit_result()
→ wait_for_task()

禁止：

server push message。

---

## 4. Blocking Pull（非常重要）

---

不能疯狂轮询。

必须：

> blocking wait。

例如：

wait_for_task(timeout=300)

server：

* 无任务时阻塞
* 有任务时返回

这是系统核心协议。

---

## 5. 单 Active Session（重要）

---

系统只允许：

> ONE ACTIVE SESSION

禁止：

多个讨论并行。

允许：

archive session
→ create new session

原因：

* 降低复杂度
* 避免 context routing
* 避免 multi-session orchestration
* 保持 SQLite 可行性

---

## 6. SQLite-first（重要）

---

默认数据库：

SQLite。

不是 PostgreSQL。

原因：

* 单机系统
* 单 active session
* 有限轮次
* 低复杂度优先
* 易部署
* 易调试

允许未来抽象：

StorageBackend
├── SQLiteBackend
└── PostgreSQLBackend

但：

> SQLite 必须是默认实现。

---

## 7. Agent 是 Persistent Participant

---

Agent 生命周期：

启动 agent
→ /register
→ 加入讨论
→ 持续参与
→ 讨论结束 or agent 主动退出

不是：

task-level subprocess invoke。

而是：

> 长生命周期 participant。

---

## 8. MCP Server 驱动整个循环

---

Loop 的控制权在 MCP Server。

不是 agent 自治。

即：

server 决定：

* 当前 phase
* 当前 round
* 下一个 task
* 是否停止
* consensus
* bias assignment

agent：

只负责：

> 完成当前 task。

---

## 9. Runtime Bias（重要）

---

所有 agent 使用统一 SKILL.md。

不要多个 skill。

但是：

MCP Server 可以动态分配 bias。

例如：

* security
* maintainability
* simplicity
* scalability
* DX
* operability
* cost
* performance

bias：

属于 runtime task metadata。

不是 skill 的一部分。

---

## 10. Discussion = Workflow

---

讨论不是持续聊天。

讨论是：

proposal
→ critic
→ revision
→ optimization
→ devil advocate
→ consensus

组成的有限状态机。

==================================================

# 三、SKILL.md（核心）

==================================================

系统必须包含：

> 统一 SKILL.md

这个 skill 不是普通开发 skill。

它实际上是：

> Debate Protocol Specification

即：

定义 agent 如何参与整个讨论。

SKILL.md 必须至少包含：

---

## 1. Agent 生命周期

---

/register
wait_for_task
submit_result
leave_session

---

## 2. Discussion Rules

---

例如：

* 禁止礼貌性认同
* 必须 challenge
* 必须提出 alternative
* 必须给出 reason
* 必须结构化输出
* 禁止自由散文式回答

---

## 3. Phase Rules

---

proposal phase：

* 禁止读取其他 proposal

critic phase：

至少：

* 3 risks
* 2 missing concerns
* 1 alternative proposal

revision phase：

必须：

* accept/reject
* explain why

optimization：

必须：

* complexity analysis
* simplification opportunities

---

## 4. Output Schema

---

必须：

结构化 YAML / JSON。

禁止自由文本。

---

## 5. Consensus Rules

---

如何：

* 判断收敛
* 结束讨论
* 归档 session

---

## 6. Runtime Behavior

---

例如：

wait_for_task()
必须阻塞等待。

Agent 不允许：

* 自主开启新 phase
* 自主广播消息
* 自主修改 workflow

==================================================

# 四、你的任务

==================================================

请完成以下内容。

---

## Part 1：批判性分析

---

分析当前架构可能存在的问题：

* push model 问题
* websocket 问题
* long-lived session 风险
* agent coupling
* orchestration complexity
* context drift
* polling vs blocking
* failure recovery

---

## Part 2：重构后的系统架构

---

请设计：

新的完整架构。

必须包含：

* MCP runtime backend
* orchestration
* task inbox
* blocking pull protocol
* state machine
* agent lifecycle
* runtime bias
* session archive
* SQLite storage
* event sourcing
* failure recovery

---

## Part 3：ASCII 架构图

---

必须提供：

完整架构图。

---

## Part 4：SKILL.md 完整设计

---

必须给出：

完整的 SKILL.md 示例。

包括：

* register protocol
* wait_for_task protocol
* submit_result protocol
* phase rules
* structured output rules
* discussion constraints

---

## Part 5：数据模型设计

---

SQLite schema。

包括：

* sessions
* tasks
* events
* artifacts
* consensus
* agent_registry

---

## Part 6：状态机设计

---

完整 phase transition。

包括：

* proposal
* critic
* revision
* optimization
* devil advocate
* consensus
* archive

---

## Part 7：MCP Tool 设计

---

至少包括：

register_agent
wait_for_task
submit_result
heartbeat
get_context
leave_session
archive_session
create_session

==================================================

# 五、实现要求

==================================================

要求：

* Python
* FastAPI
* AsyncIO
* SQLite-first
* Pydantic schema
* Strong typing
* Minimal dependencies

优先：

> 可运行 MVP。

不要：

* Kubernetes
* 微服务
* 分布式系统
* websocket infra
* event bus overengineering

==================================================

# 六、最终输出要求

==================================================

请输出：

1. 重构后的完整架构文档
2. SKILL.md 完整内容
3. 状态机设计
4. MCP tool 协议
5. SQLite schema
6. 项目目录结构
7. P0-P3 实现路线图
8. 风险与技术债分析

不要只给建议。

直接输出：

> 可实施设计。
