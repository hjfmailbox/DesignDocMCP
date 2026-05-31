# Next Phase Plan

> 生成于 2026-05-31
> 上一阶段计划（Phase C — Deterministic Session Replay Engine，4 个 loops）已全部完成并归档于 git 历史
> 方向：Phase D — Operational Readiness: Session Diagnostics, Health Checks & Observability Foundation

## Excluded Scope

以下项目明确排除：

| 项目 | 排除理由 |
|------|----------|
| PDF 导出 | 属于 Phase D+ 产品化 |
| 数据模型变更（models.py） | 诊断应在现有模型上工作 |
| 第三方监控集成（Prometheus/DataDog） | 超出当前基础设施范围 |
| 性能 profiling | 独立阶段 |

---

## Loop 1 — Implement session diagnostics engine

**Status:** completed
**Priority:** P1

**Goal:** 在 `engine.py` 中添加 `get_session_diagnostics(session_id)` 方法，返回结构化诊断对象（health_score 0–100、stall_status、data_consistency、warnings 列表），利用 Phase C 的 replay 基础设施检测异常。

**Files:**
- `src/designdoc_mcp/engine.py`
- `tests/test_engine.py`

**Diagnostics Model:**

返回的 `DiagnosticsResult` 为 `dict`，字段如下：

| 字段 | 类型 | 说明 |
|------|------|------|
| `health_score` | `int` | 0–100。加权公式：`data_consistency ? 40 : 0` + `workflow_completeness_score` (0–30) + `stall_penalty` (0 或 30)。若 consistency 失败则封顶 50。 |
| `stall_status` | `dict` | `{"is_stalled": bool, "seconds_since_activity": int, "threshold_seconds": int}` |
| `data_consistency` | `dict` | `{"valid": bool, "mismatches": list[str]}`，直接复用 `validate_session_consistency` 输出 |
| `warnings` | `list[dict]` | 每项 `{"category": str, "message": str}`。bounded 上限 10 条，按 severity 排序。 |
| `workflow_progress` | `dict` | `{"current_phase": str, "has_requirement": bool, "agent_count": int, "terminal_phase": bool}` |

**Stalled Definition:**
- 基准时间字段：`session.last_active_at`
- 阈值：`300` 秒（5 分钟）
- 仅检测 `status` 为 `ACTIVE` 或 `HUMAN_REVIEW` 的 session
- 判定：`now() - parse(last_active_at) > 300 seconds`

**Read-Only Safety Guarantee:**
- `get_session_diagnostics` 不得通过 `_get()` 加载 session（避免触发 consistency validation 的 warning log 副作用）。
- 应使用 `store.get_session()` 加载，然后对 snapshot/deepcopy 执行 replay 计算，确保零 mutation。
- 实现中禁止直接修改 `session.events`、`session.current_phase`、`session.status` 等任何字段。

**Validation:**
- 健康 session（完整 debate 后）返回 health_score=100，warnings 为空
- 数据不一致 session（手动篡改 derived state 后）检测到 mismatch 并报告在 warnings 中
- stalled session（`last_active_at` 超过 300 秒前）返回 `stall_status.is_stalled=true`
- 非 stalled active session 返回 `stall_status.is_stalled=false`
- 连续调用两次 `get_session_diagnostics` 之间，session 的 phase、round、status、events.length 无任何变化
- 现有 115 个测试全部通过

---

## Loop 2 — Expose diagnostics via REST API

**Status:** completed
**Priority:** P1

**Goal:** 添加 `GET /api/sessions/{id}/diagnostics` 和 `GET /api/sessions/stalled` 端点，将 Loop 1 的诊断能力暴露给客户端。

**Files:**
- `src/designdoc_mcp/web.py`
- `src/designdoc_mcp/engine.py`（如需添加 `list_stalled_sessions()`）
- `tests/test_api_e2e.py`

**Implementation Constraint:**
`list_stalled_sessions()` 不得通过 `_get()` 遍历 sessions（避免触发 consistency validation 的 warning log 副作用和性能开销）。应直接读取 store 中的 session 列表（如 `store.list_sessions()` 或扫描数据目录），仅对疑似 stalled 的 session 按需加载元数据并计算诊断。

**Validation:**
- E2E 测试验证 `/diagnostics` 返回正确 JSON 结构（health_score, stall_status, warnings）
- E2E 测试验证 `/stalled` 只返回符合条件的 session
- E2E 测试验证无 stalled session 时 `/stalled` 返回 `[]`
- 404 session 返回标准 HTTP 404
- 现有 115+ 测试全部通过

---

## Loop 3 — Render diagnostics in frontend

**Status:** completed
**Priority:** P2

**Goal:** 在 `static/index.html` 的 session detail 页面添加 diagnostics 卡片，显示 health score（颜色编码）、stall 状态、warnings 列表。

**Files:**
- `src/designdoc_mcp/static/index.html`

**Validation:**
- 页面加载后 diagnostics 卡片可见
- health score 颜色渲染与后端 `DiagnosticsResult.color_threshold` 一致：green ≥80, yellow 50–79, red <50（阈值由 Loop 1 的后端模型统一定义，前端只做映射）
- warnings 非空时显示警告列表
- 手动验证 stalled session 显示正确状态标签

---

## Notes

- Loop 1 是核心能力，Loop 2 是 API 暴露，Loop 3 是前端呈现。
- 所有 loops 完成后，建议运行 `/dev-save` 同步协议状态。
- 本阶段不修改 `models.py`、store 序列化格式。
