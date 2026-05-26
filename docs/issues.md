# DesignDoc MCP 系统评估与问题跟踪

> 版本: v1.0 | 评估日期: 2026-05-18 | 评估范围: 全系统代码审计

---

## 一、审计总结

| 严重程度 | 数量 | 状态 |
|----------|------|------|
| **P0 致命** | 3 | ✅ 已修复 |
| **P1 高** | 5 | ✅ 已修复 5 / 📋 待修复 0 |
| **P2 中** | 11 | ✅ 已修复 9 / 📋 待修复 2 |
| **P3 低** | 5 | 📋 待规划 |

---

## 二、已修复问题

### P0-1: 文件锁机制完全失效 ✅

**文件**: `store.py` | **修复**: 2026-05-18

**问题**: `_acquire_lock` 使用 `Path.write_text()` 以 `'w'` 模式打开文件，总是覆盖已存在的文件，不会抛出 `FileExistsError`。锁形同虚设，并发写入会导致数据丢失。

**修复方案**:
- 使用 `os.open()` + `O_CREAT | O_EXCL | O_WRONLY` 实现原子性文件创建
- `_save` 改用 `tempfile.mkstemp` + `shutil.move` 实现原子写入（写临时文件 + rename）
- 异常静默吞没改为 `logger.warning` 记录

### P0-2: Web API 参数传递错误 ✅

**文件**: `web.py` | **修复**: 2026-05-18

**问题**:
- `human_decision_api`: `reason` 被当作 `approver` 传入；`human_override` 缺少 `decision` 和 `rationale` 参数，运行时 TypeError
- `resolve_question_api`: 传了4个参数但方法只接受3个，运行时 TypeError
- `review_assumptions_api`: 返回值误导（`reviewed: 1` 即使 choices 为空）

**修复方案**: 修正所有参数传递，匹配 engine 方法签名

### P0-3: Web API 零认证 ✅

**文件**: `web.py` | **修复**: 2026-05-18

**问题**: 所有 API 端点无认证，任何人可审批/拒绝/覆盖决策

**修复方案**:
- 新增 `_verify_token` 依赖，支持 `Authorization: Bearer <token>` 和 `?token=<token>` 两种方式
- 所有写操作端点添加 `Depends(_verify_token)`
- 通过环境变量 `DESIGNDOC_API_TOKEN` 配置，未设置时不启用认证（本地开发友好）

### P1-1: 共识死锁 ✅

**文件**: `engine.py` | **修复**: 2026-05-18

**问题**: 3个Agent投票 1 agree + 1 disagree + 1 needs_clarification 时，不满足任何条件，Session卡在CONSENSUS阶段。ABSTAIN投票完全未处理。

**修复方案**:
- 新增"同意+弃权"场景：`agrees > 0 and (disagrees + needs_clarification) == 0` → 完成
- 新增"部分同意"场景：`(disagrees + needs_clarification) >= 1 and agrees >= 1` → HUMAN_REVIEW
- ABSTAIN 纳入统计

### P1-2: 全局单例重复 ✅

**文件**: `web.py` | **修复**: 2026-05-18

**问题**: `server.py` 和 `web.py` 各自维护独立的 `_store` 和 `_engine`，两个 `SessionStore` 实例指向同一目录但内存缓存独立，数据不同步。

**修复方案**: `web.py` 的 `_get_store()` 和 `_get_engine()` 委托给 `server.py` 的同名函数，确保全局唯一实例

### P1-3: register_agent 无阶段限制 ✅

**文件**: `engine.py` | **修复**: 2026-05-18

**问题**: 可以在任何阶段（包括 CONSENSUS、COMPLETED）注册新 agent，破坏阶段完成检查逻辑。

**修复方案**: `register_agent` 增加阶段检查，禁止在 CRITIC/REVISION/OPTIMIZATION/DEVILS_ADVOCATE/CONSENSUS 阶段注册，禁止在 COMPLETED/ARCHIVED 状态注册。

### P1-4: human_reject 不重置阶段数据 ✅

**文件**: `engine.py` | **修复**: 2026-05-18

**问题**: 拒绝后回到 CRITIC 阶段，跳过了 PROPOSAL 阶段，旧轮次数据可能导致自动推进条件提前满足。

**修复方案**: `human_reject` 时重置到 PROPOSAL 阶段（而非 CRITIC），`current_round += 1`，重新分配视角 `_assign_perspectives(session)`。

---

## 三、待修复问题

### P2-1: Session 默认状态不一致 ✅

**文件**: `models.py` | **优先级**: 中 | **修复**: 2026-05-20

**问题**: `status` 默认 `CREATED`，但 `current_phase` 默认 `CLARIFY_IDENTIFY`，语义矛盾。

**修复方案**: `current_phase` 默认值改为 `CREATED` 对应的初始值，或增加 `NOT_STARTED` 阶段

### P2-2: 数值字段无范围校验 ✅

**文件**: `models.py` | **优先级**: 中 | **修复**: 2026-05-19

**问题**: `confidence`、`risk_score` 等字段可传入负数或大于1的值。

**修复方案**: 使用 `Field(ge=0.0, le=1.0)` 约束

### P2-3: 文档生成空架构 ✅

**文件**: `document.py` | **优先级**: 中 | **修复**: 2026-05-19

**问题**: 无 proposals/revisions 时，"Final Architecture" 标题下完全空白。

**修复方案**: 无数据时跳过该章节或显示"待辩论后生成"

### P2-4: EventBus 非线程安全 ✅

**文件**: `events.py` | **优先级**: 中 | **修复**: 2026-05-19

**问题**: `_subscribers` 是普通 dict，并发修改可能导致 RuntimeError。

**修复方案**: 使用 `threading.Lock` 保护 `_subscribers` 修改操作

### P2-5: 性能瓶颈 - 每次 get_session 都从磁盘重新加载 ✅

**文件**: `store.py` | **优先级**: 中 | **修复**: 2026-05-19

**问题**: `get_session` 每次调用都执行 `_reload_session`（读文件 + JSON解析 + Pydantic验证），是系统最大性能瓶颈。

**修复方案**: 引入文件修改时间检查（`st_mtime`），仅在文件变更时重新加载

### P2-6: list_sessions 每次重载所有 session ✅

**文件**: `store.py` | **优先级**: 中 | **修复**: 2026-05-20

**问题**: 每次调用都重新读取所有 JSON 文件，无分页支持。

**修复方案**: 已添加 `limit` / `offset` 分页参数

### P2-7: _check_phase_completion 中 CLARIFY_IDENTIFY 重复计算 ✅

**文件**: `engine.py` | **优先级**: 中 | **修复**: 2026-05-19

**问题**: 统计所有轮次的 assumptions 而非仅当前轮次，可能导致提前推进。

**修复方案**: 已按 `clarify_round` 过滤

### P2-8: generate_design_document 不验证 session 状态 ✅

**文件**: `web.py` | **优先级**: 中 | **修复**: 2026-05-26

**问题**: 可以在 CREATED 状态就生成文档，产出不完整输出。

**修复方案**: 已在 `POST /generate-document` 端点添加状态检查，非 `COMPLETED` / `HUMAN_REVIEW` 状态返回提示信息

### P2-9: submit_challenge 无目标验证 ✅

**文件**: `engine.py` | **优先级**: 中 | **修复**: 2026-05-19

**问题**: `submit_challenge` 不验证 `target_agent_id` 和 `target_proposal_id` 是否存在，也不禁止自我挑战和重复提交。可传入任意字符串作为目标。

**修复方案**: 已添加 target_agent_id 存在性检查、target_proposal_id 存在性检查、禁止 target_agent_id == agent_id

### P2-10: submit_assumptions 重复检查逻辑有误 ✅

**文件**: `engine.py` | **优先级**: 中 | **修复**: 2026-05-19

**问题**: 重复提交检查过滤条件 `a.agent_id == agent_id and session.clarify_round` 中，`session.clarify_round` 是整数始终为 truthy，实际效果是同一 agent 在任何轮次只能提交一次假设，阻止了多轮澄清（MAX_CLARIFY_ROUNDS=3）的正常工作。

**修复方案**: Assumption 模型增加 `clarify_round` 字段，重复检查改为 `a.agent_id == agent_id and a.clarify_round == session.clarify_round`

### P2-11: _save 不更新 mtime 缓存 ✅

**文件**: `store.py` | **优先级**: 中 | **修复**: 2026-05-19

**问题**: `_save` 方法只更新 `_sessions` 内存缓存，不更新 `_mtimes` 缓存。后续 `_reload_session` 会因磁盘 mtime 比缓存新而不必要地重新读取和解析 JSON 文件，即使内存中已有最新数据。

**修复方案**: 在 `_save` 末尾添加 `self._mtimes[session.session_id] = path.stat().st_mtime`

---

## 四、待规划功能

### P3-1: Agent 主动退出

当前没有 `deregister_agent` 操作。Agent 只能通过超时被动变为 inactive。

**方案**: 新增 `deregister_agent` 工具，将 agent 标记为 inactive 并触发 `_check_phase_completion`

### P3-2: Session 暂停/恢复

长时间运行的协作可能需要暂停（如午休、隔天继续）。

**方案**: 新增 `pause_session` / `resume_session`，暂停时冻结超时计时器

### P3-3: 导出格式多样化

只支持 Markdown 输出，缺少 PDF、HTML、DOCX 等格式。

**方案**: 集成 `pandoc` 或 `weasyprint` 支持多格式导出

### P3-4: Session 删除

`store.delete_session` 存在但未暴露为 MCP 工具。

**方案**: 新增 `delete_session` MCP 工具

### P3-5: 操作回滚/撤销

误操作（如错误投票、误提交 proposal）无法撤回。

**方案**: 基于事件溯源实现 undo，回退到指定事件点

---

## 五、被忽略的使用场景

### 场景 A: 单Agent自审

当前要求至少2个Agent。但有时用户希望单个Agent对自己提出的方案进行自我审视。

**方案**: 允许1个Agent启动，自动分配2个不同视角，Agent从两个视角分别提交proposal

### 场景 B: 渐进式需求

用户先提出模糊需求，澄清后追加更详细的子需求，形成树状需求结构。

**方案**: `add_requirement_delta` 支持层级关系，子需求可独立进入辩论

### 场景 C: 方案对比

多个Session讨论同一需求的不同方案，需要跨Session对比。

**方案**: 新增 `compare_sessions` 工具，生成对比文档

### 场景 D: 离线Agent

Agent可能因为网络问题暂时离线，重新连接后需要同步错过的事件。

**方案**: `get_session_flow` 返回指定事件ID之后的事件，Agent可增量同步

### 场景 E: 多人审核

当前人类审核是单人操作。实际可能需要多人投票审核。

**方案**: 人类审核也采用投票机制，支持多审核者

---

## 六、实现规划

### v1.1 — 稳定性修复（优先）

| 任务 | 优先级 | 复杂度 | 状态 |
|------|--------|--------|------|
| register_agent 阶段限制 | P1 | 低 | ✅ 已修复 |
| human_reject 数据重置 | P1 | 中 | ✅ 已修复 |
| Session 默认状态修正 | P2 | 低 | ✅ 已修复 |
| 数值字段范围校验 | P2 | 低 | ✅ 已有约束 |
| 文档生成空架构处理 | P2 | 低 | ✅ 已有占位 |
| CLARIFY_IDENTIFY 轮次过滤 | P2 | 低 | ✅ 已修复 |
| generate_design_document 状态检查 | P2 | 低 | ✅ 已修复 |

### v1.2 — 性能与健壮性

| 任务 | 优先级 | 复杂度 | 状态 |
|------|--------|--------|------|
| get_session 增量加载（mtime检查） | P2 | 中 | ✅ 已修复 |
| list_sessions 分页 | P2 | 中 | ✅ 已实现 |
| EventBus 线程安全 | P2 | 低 | ✅ 已修复 |
| deregister_agent | P3 | 低 | ✅ 已实现 |
| delete_session MCP工具 | P3 | 低 | ✅ 已实现 |
| submit_challenge 目标验证 | P2 | 低 | ✅ 已修复 |
| submit_assumptions 重复检查修复 | P2 | 低 | ✅ 已修复 |
| _save 更新mtime缓存 | P2 | 低 | ✅ 已修复 |

### v1.3 — 场景扩展

| 任务 | 优先级 | 复杂度 | 状态 |
|------|--------|--------|------|
| 单Agent自审模式 | P3 | 中 | ✅ 已实现 |
| 离线Agent增量同步 | P3 | 中 | ✅ 已有rejoin机制 |
| Session 暂停/恢复 | P3 | 中 | ✅ 已实现 |
| 多格式导出 | P3 | 高 | 📋 待规划 |
| 跨Session对比 | P3 | 高 | 📋 待规划 |
| 多人审核 | P3 | 高 | 📋 待规划 |
| 操作回滚 | P3 | 高 | 📋 待规划 |

### v2.0 — 按分歧点决策（详见 [decision-points.md](decision-points.md)）

| 任务 | 优先级 | 复杂度 | 依赖 |
|------|--------|--------|------|
| DecisionPoint/DecisionOption 数据模型 | P2 | 低 | — |
| Session 添加 decision_points 字段 | P2 | 低 | 数据模型 |
| Critic 阶段提交逻辑扩展 | P2 | 中 | 数据模型 |
| _merge_decision_points 汇总去重 | P2 | 中 | Critic扩展 |
| API 序列化 + /resolve-decision-point | P2 | 中 | 汇总逻辑 |
| Critic 阶段提示词 + SKILL.md 更新 | P2 | 低 | Critic扩展 |
| 前端决策卡片界面 | P2 | 高 | API |
| 关联约束实时校验 | P3 | 高 | 前端界面 |
| 一键采纳多数方案 | P3 | 低 | 前端界面 |

### v2.1 — 存储与性能优化

| 任务 | 优先级 | 复杂度 | 依赖 |
|------|--------|--------|------|
| SQLite 存储后端完善（事务、迁移） | P2 | 高 | sqlite_store.py |
| list_sessions 分页 | P2 | 中 | — |
| 关键常量环境变量化（第八节） | P2 | 低 | — |
| Docker/start.sh 传输协议更新（SSE→HTTP） | P2 | 低 | — |
| _serialize_session 响应结构规范化 | P2 | 中 | — |
| web.py 缺失的10个API端点补录到spec | P2 | 低 | — |

### v2.2 — 质量与可观测性

| 任务 | 优先级 | 复杂度 | 依赖 |
|------|--------|--------|------|
| 日志分层（心跳独立文件） | P2 | 低 | — |
| 新增 MCP Prompt: designdoc_guide 补录到spec | P2 | 低 | — |
| 新增 MCP Resource: designdoc://active-session 补录到spec | P2 | 低 | — |
| DIMENSION_DESCRIPTIONS 补录到spec | P3 | 低 | — |
| PHASE_DESCRIPTIONS 细节同步 | P3 | 低 | — |
| 单元测试覆盖率提升 | P2 | 高 | — |
| Playwright E2E 测试 | P3 | 高 | — |

---

## 七、文档组织

当前项目文档集中放置在 `docs/` 目录：

| 文档 | 内容 |
|------|------|
| `docs/specification.md` | 技术规格（项目实现的唯一权威参考） |
| `docs/design-v1.md` | 原始设计文档（项目初始设计蓝图） |
| `docs/decision-points.md` | 按分歧点决策功能规划 |
| `docs/issues.md` | 本文档（问题跟踪 + 实现规划） |
| `docs/restructure.md` | 架构重构方案 |
| `data/examples/digital-twin.md` | 外部测试需求文档示例 |

---

## 八、关键常量配置化

| 常量 | 当前值 | 建议环境变量 | 默认值 |
|------|--------|-------------|--------|
| `AGENT_INACTIVE_TIMEOUT_SECONDS` | 300 | `DESIGNDOC_AGENT_TIMEOUT` | 300 |
| `CLARITY_THRESHOLD` | 0.7 | `DESIGNDOC_CLARITY_THRESHOLD` | 0.7 |
| `CLARITY_DIMENSIONS` | 10个 | - | - |
| `PERSPECTIVES` | 8个 | - | - |
| `DESIGNDOC_PORT` | 8765 | `DESIGNDOC_PORT` | 8765 |
| `DESIGNDOC_API_TOKEN` | 空 | `DESIGNDOC_API_TOKEN` | 空(不启用) |
