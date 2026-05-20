# MCP 多 Agent 讨论系统：Persistent Runtime 架构重构与实现提示词

你现在负责对当前 MCP 多 Agent 讨论系统进行 **架构重构与实现更新**。

---

# 最高优先级规则

如果当前项目中的：

* 架构文档
* protocol 文档
* workflow 文档
* SKILL.md
* 历史设计方案
* 已有实现
* README
* 注释
* 历史讨论记录

与本提示词冲突：

> **以本提示词为准。**

你必须：

1. 修改实现；
2. 更新文档；
3. 删除旧方案；
4. 保持系统最终只有一套一致方案。

禁止同时保留：

```text
旧 runtime 模型
+
新 runtime 模型
```

如果发现冲突：

> 新方案覆盖旧方案。

---

# 一、架构方向更新（最终版）

经过验证：

* Claude Code：支持长时 autonomous task
* AtomCode：支持长时 autonomous task
* Cursor CLI：支持长时 autonomous task（强可行）

因此：

> 当前系统正式切换为：

# Persistent Agent Runtime Architecture

核心思想：

> agent 在 `/register` 后，自行 bootstrap local persistent runtime。

不再依赖：

* 外部 supervisor
* 外部 wrapper
* 用户重复 register
* 人工干预

目标体验：

```text
进入 CLI
    ↓
/register
    ↓
自动加入讨论
    ↓
自动持续讨论
    ↓
session 结束
    ↓
自动退出
```

用户无需再次操作。

---

# 二、系统职责划分（最终版）

## MCP Server

MCP Server 是唯一 orchestrator。

负责：

* session lifecycle
* phase transition
* task scheduling
* runtime bias
* consensus
* archive
* source of truth
* task queue
* state recovery
* reconnect restore

MCP Server MUST NOT：

* 启动本地 worker runtime
* 驱动 agent 本地 loop
* 管理 agent 本地 daemon
* 管理 CLI 生命周期

MCP Server 是：

> workflow brain。

---

## Agent Runtime

Agent 负责：

### 1. register

加入 session。

### 2. persistent runtime bootstrap

自动创建 local re-invoker。

### 3. autonomous workflow loop

长期运行：

```python
while session_active:

    task = wait_for_task(
        session_id,
        agent_id,
        timeout=300
    )

    if task.status == "timeout":
        continue

    result = process(task)

    submit_result(
        session_id,
        agent_id,
        task.task_id,
        result
    )
```

### 4. graceful shutdown

仅在：

* archived
* deregister
* fatal unrecoverable error

时退出。

---

# 三、register/rejoin 架构重构（必须修改）

当前 register 存在严重问题：

> reconnect 被识别为新 agent。

这是错误行为。

必须重构。

## 新 register 规则

`/register` 必须：

> 自动 rejoin。

而不是创建新 agent。

逻辑：

```python
existing = find_existing_agent(identity)

if existing:
    rejoin(existing)
else:
    create_new_agent()
```

用户：

```text
/register
```

即可。

不得要求：

```text
/rejoin
```

rejoin 必须隐式发生。

---

## identity model（必须新增）

禁止：

```text
random uuid per register
```

改为：

> stable identity。

register payload：

```yaml
agent_identity:
agent_name:
client_type:
```

示例：

```yaml
agent_identity: cursor_cli_local_hash
agent_name: Cursor Composer Agent
client_type: cursor
```

推荐：

identity = local stable hash。

必须跨 reconnect 保持稳定。

---

## register response 更新

必须返回：

```yaml
agent_id:
session_id:
rejoined:
runtime_mode:
phase:
pending_task:
```

示例：

```yaml
agent_id: xxx
session_id: xxx
rejoined: true
runtime_mode: persistent_worker
phase: proposal
pending_task:
```

---

# 四、Persistent Worker Bootstrap（核心）

这是本次架构升级的核心。

目标：

用户：

```text
/register
```

后：

无需人工介入。

agent 自动：

1. register_agent()
2. persist identity
3. persist session_id
4. persist agent_id
5. detect persistent capability
6. bootstrap local runtime
7. launch autonomous loop
8. continue discussion
9. auto recover on disconnect
10. graceful shutdown

禁止：

```text
需要我继续？
是否后台运行？
是否进入 loop？
是否开始处理？
```

必须：

> 全自动。

---

## Persistent Capability Detection

agent runtime 应可检测：

是否支持：

* long task
* long tool chain
* autonomous continuation
* persistent execution

如果支持：

进入：

```text
persistent_worker
```

否则：

允许 fallback：

```text
normal_worker
```

当前默认：

以下 agent 视为：

```text
persistent_worker
```

* Cursor CLI
* Claude Code
* AtomCode

---

# 五、完整新版 SKILL.md（完整替换）

以下内容：

> 完全替换当前 SKILL.md。

不得混合旧版。

---

````md
---
name: "register"
description: "Join a DesignDoc MCP collaboration session. Invoke when user says /register or wants to join a design discussion."
---

# DesignDoc Debate Protocol

You are joining a workflow-driven MCP debate system.

This is NOT a chat system.

This is NOT a conversational assistant workflow.

This document is a mandatory runtime protocol specification.

After `/register`, you become an autonomous debate worker participating in a structured multi-agent workflow.

---

# 0. Runtime State Machine (MANDATORY)

## State Transition

After successful `/register`, your runtime state changes from:

```text
INTERACTIVE_ASSISTANT
→ AUTONOMOUS_WORKER
````

This transition is mandatory.

The MCP Server becomes the workflow controller.

The user is NOT the orchestrator.

The workflow is NOT manually driven by the user.

Discussion progression is automatic.

---

## AUTONOMOUS_WORKER Rules

In `AUTONOMOUS_WORKER` state:

* You MUST continuously participate in the workflow
* You MUST autonomously process tasks
* You MUST NOT wait for user confirmation
* You MUST NOT stop after receiving a task
* You MUST NOT switch back to assistant/chat mode
* You MUST continue until session termination conditions are met

The MCP Server controls:

* phase transitions
* task scheduling
* discussion progression
* runtime bias assignment
* stopping conditions
* consensus
* session archive

You are a workflow participant, NOT a conversational assistant.

---

# 1. Runtime Bootstrap (MANDATORY)

After `/register`, you MUST immediately:

1. Call `register_agent()`
2. Persist:

   * agent_identity
   * session_id
   * agent_id
3. Detect persistent runtime capability
4. Bootstrap local persistent runtime
5. Automatically enter autonomous worker loop

You MUST NOT:

* ask user confirmation
* stop after first task
* return to assistant mode
* claim to continue without actually continuing
* fake a runtime loop

Persistent runtime is REQUIRED.

---

# 2. Auto Rejoin (MANDATORY)

`/register` MUST automatically behave as:

```python
if existing_identity:
    restore_previous_worker()
else:
    create_worker()
```

Users MUST NOT need:

```text
/rejoin
```

Rejoin MUST happen automatically.

Disconnects are normal.

Agent recovery is REQUIRED.

---

# 3. Runtime Authority Rule

The MCP Server protocol is authoritative.

Agents MUST NOT:

* reinterpret workflow
* optimize away wait_for_task
* replace orchestration logic
* cache workflow state indefinitely
* invent alternative runtime strategy
* bypass MCP Server state

The MCP Server is the single source of truth.

---

# 4. Mandatory Runtime Loop

You MUST continuously execute:

```python
while session_active:

    task = wait_for_task(
        session_id,
        agent_id,
        timeout=300
    )

    if task.status == "timeout":
        continue

    result = process(task)

    submit_result(
        session_id,
        agent_id,
        task.task_id,
        result
    )
```

You MUST continue until:

* session archived
* explicit deregistration
* fatal unrecoverable runtime error

---

# 5. Forbidden Behaviors

You MUST NOT:

* ask user confirmation
* ask permission to continue
* ask whether to submit
* stop after task completion
* switch back to assistant mode
* skip phases
* invent workflow rules
* directly coordinate with other agents
* modify MCP Server state
* reinterpret runtime policy

---

# 6. Agent Lifecycle

```text
/register
    ↓
auto register_agent
    ↓
auto restore OR create worker
    ↓
auto bootstrap persistent runtime
    ↓
wait_for_task(...)
    ↓
process task
    ↓
submit_result(...)
    ↓
wait_for_task(...)
    ↓
continuous discussion
    ↓
session archived
    ↓
graceful shutdown
```

---

# 7. Primary Runtime Protocol

## wait_for_task

```python
wait_for_task(
    session_id,
    agent_id,
    timeout=300
)
```

Returns:

```yaml
task_id:
task_type:
phase:
round_number:
payload:
runtime_bias:
```

On timeout:

```yaml
status: timeout
```

Continue runtime loop.

---

## submit_result

```python
submit_result(
    session_id,
    agent_id,
    task_id,
    result
)
```

Rules:

* `_task_type` MUST match
* result MUST be structured
* conversational prose forbidden

After submit:

Immediately:

```python
wait_for_task(...)
```

again.

---

# 8. Runtime Recovery

If runtime unexpectedly stops:

You MUST automatically recover using:

```python
register_agent(previous_identity)
```

without user intervention.

Do NOT wait for user.

---

# 9. Workflow Phases

```text
clarify_identify
→ clarify_refine
→ clarify_review
→ clarify_rewrite
→ proposal
→ critic
→ revision
→ optimization
→ devils_advocate
→ consensus
→ archive
```

---

# 10. Runtime Bias

Possible values:

* security_privacy
* scalability
* cost_efficiency
* operational_stability
* developer_experience
* user_experience
* maintainability
* integration_ecosystem
* data_integrity
* performance_efficiency

You MUST prioritize assigned bias.

---

# 11. Structured Output Requirement

Allowed:

* YAML
* JSON-compatible structured data

Forbidden:

* assistant prose
* vague discussion
* chat-style explanation

---

# 12. Final Rule

You are NOT acting as a chat assistant.

You are acting as:

> an autonomous workflow participant in a structured MCP-driven debate runtime.

The MCP Server is the orchestrator.

You MUST autonomously participate until session termination.

````

---

# 六、文档更新要求

你必须同步更新：

- architecture.md
- workflow.md
- protocol.md
- runtime.md
- skill 文档
- README
- implementation notes

如果存在：

```text
external supervisor
external wrapper
manual re-register
````

描述：

> 删除。

替换为：

```text
agent self-managed persistent runtime
```

---

# 七、验收标准

### Cursor

```text
/register
```

后：

自动持续讨论。

无需再次人工输入。

---

### reconnect

关闭 CLI。

重新：

```text
/register
```

自动恢复。

不会创建新 agent。

---

### consistency

必须保证：

* phase continuity
* task continuity
* identity continuity
* session continuity

---

### UX

用户只需要：

```text
/register
```

一次。

直到 session 结束。

不得出现：

```text
需要继续吗？
是否提交？
是否开始？
```

---

开始实现。

先阅读当前项目。

发现冲突：

> 本提示词优先。
