# Next Phase Plan

> 生成于 2026-05-30
> 上一阶段计划（4 个 product-value loops）已全部完成并归档于 git 历史
> 方向：Phase A — Bulk Human Decision（一键批量采纳多数意见）

## Excluded Scope

以下项目明确排除：

| 项目 | 排除理由 |
|------|----------|
| 前端 UI 变更 | 当前阶段仅提供 API/MCP 能力，前端消费在后续 Phase B |
| `DecisionOption` 模型字段变更 | 按 scope 要求，support_count 通过 `Session.metadata` 动态计算 |
| 除 majority 外的其他策略 | 保持 MVP，后续按需扩展 |

---

## Loop 1 — Engine bulk resolve with dynamic support counting

**Status:** completed
**Priority:** P1
**Tests:** 94 passing (89 → 94)

**Goal:** 在 engine 层实现动态 support_count 追踪与 bulk resolve 核心逻辑：`_merge_decision_points` 合并时将各选项的支持 agent 数写入 `session.metadata["decision_point_supports"]`；新增 `bulk_resolve_decision_points()` 按 majority 策略批量解决未决 decision point。

**Files:**
- `src/designdoc_mcp/engine.py`
- `tests/test_engine.py`

**Validation:**
- `test_merge_stores_support_count_in_metadata` — 合并后 metadata 中 `decision_point_supports` 正确记录各 option 的支持数
- `test_bulk_resolve_majority_picks_highest_count` — majority 策略正确选择 support_count 最高的选项
- `test_bulk_resolve_preview_does_not_modify` — `preview=True` 不修改 session 状态
- `test_bulk_resolve_fallback_without_metadata` — 历史 session 无 metadata 时回退到第一个选项
- `test_bulk_resolve_tie_breaks_to_first_option` — 并列时选择 options 列表中的第一个
- 现有 engine 测试全部通过

---

## Loop 2 — REST endpoint exposure

**Status:** pending
**Priority:** P1

**Goal:** 在 Web API 暴露 `POST /api/sessions/{session_id}/bulk-resolve-decisions` 端点，使外部工具可调用一键批量解决能力。

**Files:**
- `src/designdoc_mcp/web.py`
- `tests/test_api_e2e.py`

**Validation:**
- `test_bulk_resolve_returns_resolved_list` — 端点返回 200 及包含 `resolved` / `skipped` 的结构
- `test_bulk_resolve_invalid_session_404` — 无效 session 返回 404
- `test_bulk_resolve_preview_vs_apply` — preview 后重新获取 decision-points，human_choice 仍未设置；apply 后已设置
- 现有 E2E 测试全部通过

---

## Loop 3 — MCP tool exposure

**Status:** pending
**Priority:** P2

**Goal:** 在 MCP server 注册 `bulk_resolve_decision_points` tool，保持 MCP 与 REST 能力对等。

**Files:**
- `src/designdoc_mcp/server.py`
- `tests/test_server.py`

**Validation:**
- `test_bulk_resolve_mcp_tool_returns_resolved` — 调用 tool 返回正确结构
- `test_bulk_resolve_mcp_tool_preview_mode` — preview 参数透传正确
- 现有 server 测试全部通过

---

## Notes

- 本计划覆盖 `docs/decision-points.md` Phase 3 中定义的「一键采纳多数方案」需求。
- `support_count` 不持久化在 `DecisionOption` 中，而是动态计算后存入 `Session.metadata`，避免模型变更与序列化兼容性风险。
- 所有 loops 完成后，建议运行 `/dev-save` 同步协议状态。
