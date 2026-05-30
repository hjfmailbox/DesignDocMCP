# Next Phase Plan

> 生成于 2026-05-30
> 上一阶段计划（Phase A — Bulk Human Decision，3 个 loops）已全部完成并归档于 git 历史
> 方向：Phase B — Frontend Decision-Point Enhancement + Timeline Visualization

## Excluded Scope

以下项目明确排除：

| 项目 | 排除理由 |
|------|----------|
| 重构前端构建流程 | 当前 zero-build Alpine.js + Tailwind 足够 |
| 新增后端 API | Phase B 仅消费现有 API |
| PDF 导出 / Agent 健康面板 | 属于 Phase C/D，不在本阶段 |

---

## Loop 1 — Expose event timeline in session detail API

**Status:** completed
**Priority:** P1

**Goal:** 在 `_serialize_session()` 中新增 `event_timeline` 字段，使前端可通过现有的 session detail API 获取阶段转换时间线数据。

**Files:**
- `src/designdoc_mcp/web.py`
- `tests/test_api_e2e.py`

**Validation:**
- `test_session_detail_includes_event_timeline` — session detail 响应包含 `event_timeline` 数组，每项有 `from_phase`, `to_phase`, `timestamp`
- 新 session 的 `event_timeline` 为空列表
- 现有 E2E 测试全部通过

---

## Loop 2 — Wire frontend bulk resolve to backend endpoint

**Status:** pending
**Priority:** P1

**Goal:** 将前端 `adoptMajority()` 从 broken 的客户端逻辑替换为对 `POST /bulk-resolve-decisions` 后端端点的真实调用。

**Files:**
- `src/designdoc_mcp/static/index.html`

**Validation:**
- `adoptMajority()` 函数内发起 `fetch('/api/sessions/' + s.session_id + '/bulk-resolve-decisions', ...)` 并刷新 session
- 移除旧的客户端 label-count 逻辑
- 调用成功后 toast 提示已解决的 decision point 数量

---

## Loop 3 — Render event timeline in frontend

**Status:** pending
**Priority:** P2

**Goal:** 在 Flow 标签页（或独立区域）使用现有 `.timeline-item` CSS 渲染 `event_timeline` 数据，显示 session 的阶段转换历史。

**Files:**
- `src/designdoc_mcp/static/index.html`

**Validation:**
- Flow 标签页顶部新增 "Phase Transitions" 时间线区域
- 每个 transition 显示 `from_phase` → `to_phase` 及相对时间
- 无 transitions 时显示空状态提示
- 使用现有 `.timeline-item` / `.timeline-dot` 样式，无需新增 CSS

---

## Notes

- 前端 decision point 卡片 UI 已完整存在（`index.html:590-646`），Loop 2 仅需修复按钮的后端调用逻辑。
- `event_timeline` 字段在 `get_session_flow()` 中已生成，Loop 1 仅需将其同步到 `_serialize_session()`。
- 所有 loops 完成后，建议运行 `/dev-save` 同步协议状态。
