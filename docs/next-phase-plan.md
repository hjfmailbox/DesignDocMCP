# Next-Phase Plan

## Current Reality Snapshot

**Project**: DesignDoc MCP v0.3.0 | **Branch**: master | **Tests**: 66 passed

**What works**:
- Full 4-phase clarification + 6-phase debate flow
- Web UI with decisions, flow timeline, document preview
- MCP server with 20+ tools
- File-backed persistence with atomic writes + file locking
- SQLite backend optional
- API token auth, pagination, session pause/resume
- Single-agent self-review mode, decision-point tracking
- 4-layer document generation (design doc, ADR, summary, decisions)
- Basic undo/rollback (`revert_to_event`)
- Hierarchical requirement deltas (`parent_delta_id`)
- Runtime constants externalization (`constants.py`)
- E2E API test skeleton (`test_api_e2e.py`)
- Cross-session comparison (`compare_sessions`)
- HTML design document export (`generate_design_document_html`)
- Multi-human review voting (`submit_human_vote`)

**What drifts**:
- `docs/specification.md` task statuses aligned with code reality (Loop 1, 10)
- `docs/issues.md` P2/P3 counts and prose synced with implementation tables (Loop 2, 10)
- Documentation drift eliminated; no "documentation lying" remains

**What is genuinely missing**:
- PDF/DOCX export (HTML already implemented via `generate_design_document_html`)
- Full deterministic replay (current undo is truncation-based, not snapshot-based)

---

## Key Gaps (as of post-Loop-10)

1. **Documentation lying** — ✅ resolved via Loop 1, 2, 10 sweeps
2. **Test surface** — ✅ improved from 37 to 56 tests (Loop 4, 9); consensus/ABSTAIN/human_reject covered
3. **CLARIFY_REWRITE auto-advance** — ✅ verified correct (Loop 3); auto-advances to HUMAN_REVIEW as designed
4. **No undo** — ✅ `revert_to_event` implemented and tested (Loop 5)
5. **Requirement deltas are flat** — ✅ `parent_delta_id` support added (Loop 8)
6. **Constant externalization** — ✅ runtime constants extracted to `constants.py` (Loop 7)
7. **API completeness** — ✅ all 25 spec-defined REST routes present (Loop 6); E2E tests added (Loop 9)

---

## Recommended Focus

Documentation drift resolved. Core stabilization (Loops 1-10) and external validation (Loops 11-13) complete. 66 tests passing.

Next possible directions:
1. **v2.0 按分歧点决策** — DecisionPoint 数据模型 + Critic 阶段扩展 + 前端决策卡片
2. **PDF/DOCX 导出** — 基于已有 HTML 导出扩展多格式支持
3. **Full deterministic replay** — 将截断式 undo 升级为基于快照的精确回播

---

## Ordered Work Queue (5–10 Loops)

| Loop | Type | Task | Why |
|------|------|------|-----|
| 1 | docs sync | Audit `specification.md` task statuses against code; flip finished items to ✅ | ✅ Completed 2026-05-26 |
| 2 | docs sync | Fix `issues.md` P2 count, sync P3 prose with implementation tables, update README if needed | ✅ Completed 2026-05-26 |
| 3 | bugfix | Verify `CLARIFY_REWRITE` auto-advance in `engine.py`; fix if it does not auto-advance after all agents submit refined requirements | ✅ Completed 2026-05-26; logic verified correct, no fix needed |
| 4 | test improvement | Add tests for consensus deadlock paths, ABSTAIN handling, human_reject round reset | ✅ Completed 2026-05-26; 37→40 tests |
| 5 | feature completion | Implement basic undo: `revert_to_event(session_id, event_id)` using existing event log | ✅ Completed 2026-05-26; 40→44 tests |
| 6 | API behavior | Audit `web.py` endpoints against `specification.md`; add any missing REST routes already defined in spec | ✅ Completed 2026-05-26; all 25 routes present |
| 7 | small refactor | Finish constant externalization (`AGENT_INACTIVE_TIMEOUT_SECONDS`, `CLARITY_THRESHOLD`, etc.) from `models.py` to env vars | ✅ Completed 2026-05-27; `constants.py` created |
| 8 | state/data | Extend `add_requirement_delta` to support `parent_delta_id` for hierarchical requirements | ✅ Completed 2026-05-27; 44→48 tests |
| 9 | test improvement | Add E2E API test skeleton (pytest + httpx) covering create-session → register-agent → submit-proposal → consensus | ✅ Completed 2026-05-27; 48→56 tests |
| 10 | docs sync | Final sweep: README, spec, issues.md aligned; mark phase complete | ✅ Completed 2026-05-27; all docs synced |

---

## What NOT to Work On

- **No SQLite backend perfection** — it works; full transaction/migration polish is over-engineering for current stage
- **No PDF/DOCX export** — HTML is already implemented; PDF/DOCX is speculative
- **No frontend redesign** — Web UI is functional; visual polish is low ROI
- **No large refactor** — engine.py is large but stable; resist temptation

---

## Success Signal for Ending This Phase

This phase ends when **all of the following** are true:

1. ✅ `docs/specification.md`, `docs/issues.md`, and `README.md` accurately reflect code reality
2. ✅ `CLARIFY_REWRITE` auto-advance behavior is verified correct (or fixed)
3. ✅ Undo/rollback to a specific event is implemented and tested
4. ✅ At least 3 new integration-level tests exist for consensus and phase transitions
5. ✅ No documented P1/P2 issues remain unaddressed
6. ✅ Test count ≥ 50 (current 56, up from 37)

**Phase complete.** Stabilization (Loops 1-10) and external validation (Loops 11-13) finished. Next: choose between v2.0 decision-point features, PDF/DOCX export, or user-directed work.
