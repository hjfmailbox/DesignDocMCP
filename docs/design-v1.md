# MCP 驱动的多智能体设计评审系统（Design Review Swarm）设计文档

> **⚠️ 本文档为项目初始设计草案，已被 [specification.md](specification.md) 取代。**
>
> 以下内容与当前实现存在重大差异，仅作历史参考：
> - 存储：本文档设计 PostgreSQL → 实际实现为 JSON 文件 + SQLite 可选后端
> - 接入：本文档设计 Agent Adapter 层 → 实际实现为 MCP 协议直连
> - 流程：本文档为 6 阶段辩论 → 实际实现为 4 阶段澄清 + 6 阶段辩论
> - 角色：本文档按 Agent 绑定固定角色 → 实际实现为随机视角分配
> - 共识：本文档设计自动收敛引擎 → 实际实现为投票 + 人类裁决
> - API：本文档设计 REST API → 实际实现为 MCP 工具 + Web REST API
>
> 请以 [specification.md](specification.md) 为权威参考。

> 目标：构建一个自有 MCP 驱动的多智能体设计评审系统，用于在**设计方案阶段**进行有限轮次、多视角辩论与方案完善，最终输出高质量、可直接进入开发的设计文档。

---

# 1. 项目定位

## 1.1 核心目标

本系统不是多智能体协作开发平台。

本系统仅聚焦：

> **设计方案阶段的多 Agent 评审与辩论**

即：

- 多个 Agent 基于同一需求提出独立方案
- 通过有限轮次的结构化辩论发现遗漏与风险
- 自动收敛形成最终设计文档
- 人工审核后交给单 Agent 执行开发

最终目标：

> **最大化设计质量，而非最大化自动化程度。**

---

## 1.2 非目标（明确排除）

系统不负责：

- 多 Agent 长期协作开发
- 多 Agent 实时代码协同
- 实时聊天室
- 实时多人编辑
- IDE 协同
- 自动 merge 代码冲突
- 无限讨论
- 无人值守自治系统

这些方向复杂度极高，并非当前目标。

---

# 2. 核心理念

系统采用：

> **Document-first + Event-driven Debate**

而不是聊天室。

核心原则：

1. 独立思考优先
2. 有约束的结构化辩论
3. 有限轮次
4. 自动收敛
5. 人工最终决策
6. 全流程可追溯

系统的目标不是让 Agent 聊天。

而是：

> **让 Agent 进行高价值架构评审。**

---

# 3. 推荐协作模式

最终选择：

> **Critic-first + Optimization + Consensus**

即：

先找漏洞 → 再找更优方案 → 最后收敛。

这是设计质量最高且成本可控的模式。

---

# 4. 系统整体架构

```text
                    ┌──────────────────────┐
                    │      Human User      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   MCP Review Server  │
                    └──────────┬───────────┘
                               │
      ┌────────────────────────┼────────────────────────┐
      ▼                        ▼                        ▼
┌────────────┐        ┌────────────────┐      ┌────────────────┐
│ Debate     │        │ Consensus      │      │ Document       │
│ Orchestrator│       │ Engine         │      │ Generator      │
└──────┬─────┘        └──────┬─────────┘      └────────┬───────┘
       │                     │                           │
       └────────────┬────────┴──────────────┬───────────┘
                    ▼                       ▼
            ┌────────────────┐     ┌────────────────┐
            │ Event Store    │     │ Session Store  │
            │ PostgreSQL     │     │ PostgreSQL     │
            └────────────────┘     └────────────────┘

                    Agent Adapter Layer

      ┌──────────────┬──────────────┬──────────────┬──────────────┐
      ▼              ▼              ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ Claude   │ │ Kimi     │ │ Cursor   │ │ Trae     │
│ Adapter  │ │ Adapter  │ │ Adapter  │ │ Adapter  │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

架构原则：

> 所有 Agent 必须通过 Orchestrator 通信。

禁止 Agent 之间直接互联。

原因：

- 避免状态混乱
- 保证可审计
- 避免上下文污染
- 降低复杂度

---

# 5. 技术选型

## 5.1 后端

推荐：

```yaml
language: Python
framework: FastAPI
runtime: AsyncIO
```

原因：

- MCP 生态成熟
- Python Agent tooling 更完善
- Prompt orchestration 更容易
- 适合异步调度

Node.js 作为备选。

不推荐作为第一实现。

---

## 5.2 数据存储

推荐：

```yaml
database: PostgreSQL
```

不使用 Redis 作为主存储。

Redis：

仅允许作为：

- cache
- 临时任务队列
- rate limiting

不能作为：

> source of truth

原因：

讨论过程必须 durable 与可追溯。

---

## 5.3 容器化

推荐：

```yaml
services:
  - mcp-server
  - postgres
```

Docker Compose 即可。

暂不引入 Kubernetes。

---

# 6. Agent 接入架构

## 6.1 统一 Adapter 模式

每个 Agent 通过 Adapter 接入。

禁止直接依赖某个工具实现。

统一协议：

```text
request
  ↓
adapter
  ↓
agent
  ↓
normalized response
```

Adapter 职责：

1. Prompt 转换
2. 调用 Agent
3. 响应解析
4. 标准化输出
5. 错误恢复

这样可替换 Agent 而不影响系统。

---

## 6.2 Agent Role Bias

角色不是强约束。

只是 Prompt 偏置。

### Claude

偏向：

- 实现可行性
- 技术细节
- 风险控制

---

### Kimi

偏向：

- 架构设计
- 替代方案
- 抽象层次

---

### Cursor

偏向：

- 可维护性
- 工程结构
- 开发体验

---

### Trae

偏向：

- 工程实践
- CI/CD
- 部署
- Observability

允许 overlap。

禁止硬角色锁定。

---

# 7. 核心协作流程

## Phase 0：需求输入

用户输入：

- 原始需求
- 附加约束
- 技术偏好
- 禁止项

系统生成：

```yaml
problem_statement:
constraints:
acceptance_criteria:
open_questions:
```

作为统一输入。

---

## Phase 1：独立方案生成（Proposal）

目标：

> 避免首因效应。

规则：

所有 Agent：

> 禁止读取其他 Agent 输出。

每个 Agent 必须独立输出：

```yaml
architecture:
tech_stack:
tradeoffs:
risks:
assumptions:
unknowns:
```

保存为：

```yaml
proposal_event
```

---

## Phase 2：漏洞挑战（Critic Round）

目标：

> 强制找问题。

禁止：

```text
我同意
没有问题
方案很好
```

每个 Agent：

至少输出：

```yaml
3 risks
2 missing considerations
1 alternative proposal
```

消息格式：

```yaml
type: challenge
round: 1
source_agent:
target_agent:
priority:
category:
payload:
confidence:
```

分类：

```yaml
categories:
  - architecture
  - scalability
  - maintainability
  - performance
  - deployment
  - observability
  - cost
  - security
```

---

## Phase 3：方案修正（Revision）

目标：

> 强制吸收有效意见。

Agent 必须回答：

```yaml
accepted_feedback:
rejected_feedback:
reason:
changed_design:
```

禁止：

> 礼貌性回复。

必须产生设计变化。

---

## Phase 4：优化讨论（Optimization）

目标：

> 找更优解。

关注：

- 更简单
- 更稳定
- 更便宜
- 更可维护
- 更可扩展

输出：

```yaml
optimization:
impact:
tradeoff:
complexity_change:
```

---

## Phase 5：最终挑战（Devil’s Advocate）

系统随机指定 Agent：

强制唱反调。

Prompt：

> 假设当前方案会失败，请证明为什么。

输出：

```yaml
failure_modes:
risk_score:
mitigation:
```

这是发现隐藏问题的重要阶段。

---

## Phase 6：自动收敛（Consensus）

Consensus Engine 自动分类：

```yaml
accepted:
rejected:
alternatives:
disputed:
human_decisions:
confidence:
```

并生成：

> 最终设计决策。

---

# 8. 动态停止机制

不使用固定轮数。

采用：

> 最小轮次 + 自适应停止

策略：

```yaml
min_rounds: 4
recommended_rounds: 4-6
max_rounds: 8
```

停止条件：

满足任一即可结束。

## Condition 1

连续两轮：

```yaml
novelty_score < 0.15
```

即：

80% 内容重复。

---

## Condition 2

剩余争议：

```yaml
<= 3
```

并属于：

> 人工决策问题。

---

## Condition 3

平均置信度：

```yaml
avg_confidence > 0.8
```

---

## Hard Limit

```yaml
rounds >= 8
```

强制结束。

防止 AI 社交循环。

---

# 9. MCP 协议设计

统一事件协议：

```yaml
id:
session_id:
round:
timestamp:
type:
source_agent:
target_agent:
confidence:
payload:
references:
metadata:
```

支持事件：

```yaml
proposal
challenge
rebuttal
revision
optimization
risk
consensus
human_decision
system_event
```

---

# 10. 会话状态管理

Session State：

```yaml
session_id:
status:
current_phase:
current_round:
agents:
open_questions:
consensus_level:
created_at:
updated_at:
```

状态机：

```text
CREATED
  ↓
PROPOSAL
  ↓
CRITIC
  ↓
REVISION
  ↓
OPTIMIZATION
  ↓
FINAL_CHALLENGE
  ↓
CONSENSUS
  ↓
HUMAN_REVIEW
  ↓
FINISHED
```

---

# 11. 人工审核机制

人类拥有最终裁决权。

系统必须输出：

```yaml
human_required:
```

包括：

- 技术路线冲突
- 成本与复杂度权衡
- 高风险决策
- 无法达成一致问题

人工操作：

```yaml
approve
reject
override
force_decision
rerun_round
```

---

# 12. 输出文档结构

最终输出采用：

> Multi-layer Output

包括：

## 1. Final Design Doc

用于直接开发。

```md
# Overview
# Goals
# Constraints
# Final Architecture
# Technical Decisions
# Data Model
# API Design
# Workflow
# Risks
# Implementation Plan
# Acceptance Criteria
```

---

## 2. Architecture Decision Record

记录：

为什么这样选。

```md
# Decision
# Alternatives Considered
# Tradeoffs
# Final Choice
```

---

## 3. Debate Summary

记录：

高价值讨论。

```md
# Major Challenges
# Resolved Risks
# Key Improvements
```

---

## 4. Human Decision Points

明确需要人工判断。

---

# 13. API 草案

## Create Session

```http
POST /sessions
```

---

## Submit Requirement

```http
POST /sessions/{id}/requirements
```

---

## Start Debate

```http
POST /sessions/{id}/debate/start
```

---

## Get State

```http
GET /sessions/{id}
```

---

## Human Decision

```http
POST /sessions/{id}/decision
```

---

## Generate Final Doc

```http
POST /sessions/{id}/generate
```

---

# 14. 数据模型（建议）

主要表：

```text
sessions
agents
events
consensus
artifacts
human_decisions
```

事件溯源（Event Sourcing）：

推荐。

因为：

> 所有讨论历史天然保留。

---

# 15. 实现路线图

## P0

基础骨架

时间：1~2 天

目标：

- FastAPI
- PostgreSQL
- Session
- Event Store
- Docker

---

## P1

单 Agent 流程验证

时间：2~4 天

目标：

- Debate state machine
- Proposal
- Challenge
- Consensus

先验证流程。

---

## P2

双 Agent 辩论

时间：3~5 天

目标：

- Claude
- Kimi

验证 debate quality。

---

## P3

完整多 Agent

时间：5~10 天

目标：

- Cursor
- Trae
- Adapter 标准化

---

## P4

质量优化

时间：3~7 天

目标：

- 动态停止
- novelty detection
- better synthesis

---

# 16. 风险评估

## Risk 1：Agent 输出不稳定

概率：高

解决：

- 强结构化 prompt
- YAML schema
- retry

---

## Risk 2：讨论发散

概率：高

解决：

- 有限轮次
- challenge schema
- orchestration

---

## Risk 3：上下文污染

概率：中

解决：

- Proposal isolation

---

## Risk 4：过度复杂化

概率：高

解决：

> V1 先验证 debate framework。

不要一次性实现全自动。

---

# 17. 最终推荐

推荐路线：

> 先做“设计评审系统”，而不是“多智能体自治系统”。

核心价值在于：

> 通过有限轮、多视角、结构化辩论，显著提升设计方案质量。

开发执行仍由单 Agent 完成。

