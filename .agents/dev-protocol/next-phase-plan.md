# Next Phase Plan

> 生成于 2026-05-30
> 上一阶段计划（Phase B — Frontend Decision-Point Enhancement + Timeline Visualization，3 个 loops）已全部完成并归档于 git 历史
> 方向：Phase C — Deterministic Session Replay Engine

## Excluded Scope

以下项目明确排除：

| 项目 | 排除理由 |
|------|----------|
| 新增前端功能 | Phase C 专注后端架构可靠性 |
| 新增导出格式（PDF/HTML） | 属于 Phase D 产品化 |
| Observability/Metrics 基础设施 | 独立阶段，不在本阶段 |
| 数据模型变更（models.py） |  Replay 应在现有模型上工作，避免迁移复杂度 |

---

## Loop 1 — Implement event-driven state builder

**Status:** completed
**Priority:** P1

**Goal:** 在 `engine.py` 中提取 `_build_state_from_events(events)` 方法，接收事件列表并重建 session 的派生状态（phase、round、proposals、challenges、votes、merged_assumptions、status），完全基于事件流而非直接读取 persisted state。

**Files:**
- `src/designdoc_mcp/engine.py`
- `tests/test_engine.py`

**Validation:**
- 对现有测试 fixtures 中的 session，`_build_state_from_events(session.events)` 产生的 `phase`、`round`、`status` 与原 session 一致
- 覆盖边缘 case：空 events、单 event、多 phase transition
- 现有 101 个测试全部通过

---

## Loop 2 — Replace revert_to_event with replay-based undo

**Status:** completed
**Priority:** P1

**Goal:** 重写 `revert_to_event()`：截断 events 到目标点后，调用 Loop 1 的 builder 重建完整状态，移除所有手动 list truncation（assumptions/proposals/votes 等按 created_at 过滤）和启发式 status inference。

**Files:**
- `src/designdoc_mcp/engine.py`
- `tests/test_engine.py`

**Validation:**
- 所有 5 个现有 revert 测试（`test_revert_truncates_events_and_data`、`test_revert_resets_phase_and_status`、`test_revert_clears_derived_state`、`test_revert_truncates_deltas`、`test_revert_to_missing_event_raises`）继续通过
- `revert_to_event` 实现中不再出现手动 `created_at <= target_time` 过滤逻辑
- 回滚后 session 状态与 builder replay 结果一致

---

## Loop 3 — Validate restart recovery with replay

**Status:** pending
**Priority:** P2

**Goal:** 添加 `validate_session_consistency(session)`，对加载后的 session replay 其 events 并断言关键字段（phase、round、status、agent_count）匹配。在 engine 初始化或 `_get()` 中集成（logging-only 模式，不阻断服务）。

**Files:**
- `src/designdoc_mcp/engine.py`
- `tests/test_engine.py`

**Validation:**
- 复杂 session（多轮 debate + human review）加载后 replay 验证通过
- 验证失败时输出结构化 warning log（包含 mismatch 字段和 event count）
- 现有 101+ 测试全部通过

---

## Loop 4 — Replay determinism regression suite

**Status:** pending
**Priority:** P2

**Goal:** 创建 `tests/test_replay_determinism.py`，覆盖完整辩论生命周期的 replay 确定性验证。

**Files:**
- `tests/test_replay_determinism.py`

**Validation:**
- 至少 3 个复杂场景：完整 debate lifecycle（created → clarify → proposal → critic → revision → consensus → completed）、多轮次 human review、带 undo 的 session
- 每个场景验证：replay 后 `status`、`current_phase`、`current_round`、`events.length` 与原 session 一致
- replay 两次同一事件流，输出结果 bit-identical

---

## Notes

- Loop 1-2 是核心架构变更，Loop 3-4 是验证和加固。
- 所有 loops 完成后，建议运行 `/dev-save` 同步协议状态。
- 本阶段不修改 `models.py`、`store.py` 序列化格式、`web.py` API 契约。
