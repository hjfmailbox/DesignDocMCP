# Next Phase Plan

> 生成于 2026-05-30
> 上一版本计划已归档于 git 历史（loops 1-5 全部完成）
> 方向：产品价值优先，排除不阻塞正确性的技术债务

## Excluded Scope（明确排除）

以下技术债务项被排除，因当前不阻塞正确性：

| 项目 | 优先级 | 排除理由 |
|------|--------|----------|
| D1 deterministic replay | P1 | 架构投资，当前 undo 稳定且有测试覆盖 |
| D4 clarify rewrite round safety | P1 | 当前架构不会重入 clarify rewrite，无活跃 bug |
| D6 session recovery | P2 | 当前恢复机制稳定，无可复现故障 |
| D7 constants drift audit | P2 | 预防性维护，无活跃问题 |

---

## Loop 1 — Document quality assertions

**Status:** completed
**Priority:** P1（直接影响用户获得的文档质量）

**Goal:** 为 `generate_design_document()` 添加质量检查，确保空章节显示结构化占位提示而非完全空白，提升不完整文档的可读性。

**Files:** `src/designdoc_mcp/document.py`, `tests/test_document.py`

**Auto-execution assessment:** 符合 — 2 个文件，非架构性，行为附加，低爆炸半径。

**Validation:**
- `test_empty_sections_show_placeholders` — 无 proposals/revisions 时，Final Architecture 章节显示占位提示而非空字符串
- `test_all_required_sections_present` — 输出 Markdown 包含所有 11 个章节标题（Header, Overview, Requirement, Goals & Constraints, Assumption Decisions, Final Architecture, Technical Decisions, Data Model & API, Risks & Mitigations, Implementation Plan, Acceptance Criteria）
- 现有 78 个测试全部通过

---

## Loop 2 — Session event timeline API

**Status:** completed
**Priority:** P1（可观测性基础设施，支撑前端可视化）

**Goal:** 扩展 `get_session_flow()` 返回结构，新增 `event_timeline` 字段，按时间顺序暴露阶段转换事件，使前端可绘制辩论流程时间线。

**Files:** `src/designdoc_mcp/engine.py`, `tests/test_engine.py`

**Auto-execution assessment:** 符合 — 2 个文件，API 响应新增字段，向后兼容，低爆炸半径。

**Validation:**
- `test_timeline_contains_phase_transitions` — timeline 包含每个阶段转换的 `from_phase`, `to_phase`, `timestamp` 记录
- `test_timeline_sorted_by_time` — timeline 条目按 `created_at` 严格升序排列
- `test_timeline_empty_for_new_session` — CREATED 状态 session 返回空 timeline
- 现有 78 个测试全部通过

---

## Loop 3 — Decision points REST exposure

**Status:** pending
**Priority:** P2（完善 v2.0 按分歧点决策功能的外部可访问性）

**Goal:** 在 Web API 新增 `GET /api/sessions/{id}/decision-points` 端点，暴露当前 session 的决策分歧列表、选项和人类选择状态，使外部工具和人类审核者可直接查看待决策项。

**Files:** `src/designdoc_mcp/web.py`, `tests/test_api_e2e.py`

**Auto-execution assessment:** 符合 — 2 个文件，新增只读端点，不改变现有行为，低爆炸半径。

**Validation:**
- `test_get_decision_points_returns_list` — 端点返回 `list[dict]`，包含 `decision_id`, `topic`, `options`, `human_choice`
- `test_get_decision_points_empty_when_none` — 无 decision_points 时返回 `[]`
- `test_get_decision_points_invalid_session_404` — 无效 session 返回 404
- 现有 E2E 测试全部通过

---

## Loop 4 — MCP active-session resource

**Status:** pending
**Priority:** P2（MCP 协议完整性，specification.md 已声明但未完全验证）

**Goal:** 补全 `@mcp.resource("designdoc://active-session")` 实现，确保其返回当前活跃会话的结构化 JSON 摘要（含 session_id, title, phase, status, agent_count）。

**Files:** `src/designdoc_mcp/server.py`, `tests/test_server.py`

**Auto-execution assessment:** 符合 — 2 个文件，新增 resource 实现，不改变现有工具行为，低爆炸半径。

**Validation:**
- `test_active_session_resource_returns_json` — 访问 `designdoc://active-session` 返回有效 JSON 字符串
- `test_active_session_resource_contains_required_fields` — JSON 包含 `session_id`, `title`, `phase`, `status`, `agent_count`
- `test_active_session_resource_no_active_session` — 无活跃会话时返回提示信息
- 现有 78 个测试全部通过
