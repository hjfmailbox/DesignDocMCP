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

**Status:** pending
**Priority:** P1

**Goal:** 在 `engine.py` 中添加 `get_session_diagnostics(session_id)` 方法，返回结构化诊断对象（health_score 0–100、stall_status、data_consistency、warnings 列表），利用 Phase C 的 replay 基础设施检测异常。

**Files:**
- `src/designdoc_mcp/engine.py`
- `tests/test_engine.py`

**Validation:**
- 健康 session（完整 debate 后）返回 health_score=100，warnings 为空
- 数据不一致 session（手动篡改 derived state 后）检测到 mismatch 并报告在 warnings 中
- 长时间未活动（>阈值）的 active session 标记为 stalled
- 现有 115 个测试全部通过

---

## Loop 2 — Expose diagnostics via REST API

**Status:** pending
**Priority:** P1

**Goal:** 添加 `GET /api/sessions/{id}/diagnostics` 和 `GET /api/sessions/stalled` 端点，将 Loop 1 的诊断能力暴露给客户端。

**Files:**
- `src/designdoc_mcp/web.py`
- `src/designdoc_mcp/engine.py`（如需添加 `list_stalled_sessions()`）
- `tests/test_api_e2e.py`

**Validation:**
- E2E 测试验证 `/diagnostics` 返回正确 JSON 结构（health_score, stall_status, warnings）
- E2E 测试验证 `/stalled` 只返回符合条件的 session
- 404 session 返回标准 HTTP 404
- 现有 115+ 测试全部通过

---

## Loop 3 — Render diagnostics in frontend

**Status:** pending
**Priority:** P2

**Goal:** 在 `static/index.html` 的 session detail 页面添加 diagnostics 卡片，显示 health score（颜色编码）、stall 状态、warnings 列表。

**Files:**
- `src/designdoc_mcp/static/index.html`

**Validation:**
- 页面加载后 diagnostics 卡片可见
- health score 以颜色渲染（green ≥80, yellow 50–79, red <50）
- warnings 非空时显示警告列表
- 手动验证 stalled session 显示正确状态标签

---

## Notes

- Loop 1 是核心能力，Loop 2 是 API 暴露，Loop 3 是前端呈现。
- 所有 loops 完成后，建议运行 `/dev-save` 同步协议状态。
- 本阶段不修改 `models.py`、store 序列化格式。
