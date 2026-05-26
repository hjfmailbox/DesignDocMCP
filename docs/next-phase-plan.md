# Next-Phase Plan

## Current Reality Snapshot

**Project**: DesignDoc MCP v0.3.0 | **Branch**: master | **Tests**: 37 passed

**What works**:
- Full 4-phase clarification + 6-phase debate flow
- Web UI with decisions, flow timeline, document preview
- MCP server with 20+ tools
- File-backed persistence with atomic writes + file locking
- SQLite backend optional
- API token auth, pagination, session pause/resume
- Single-agent self-review mode, decision-point tracking
- 4-layer document generation (design doc, ADR, summary, decisions)

**What drifts**:
- `docs/specification.md` has 5+ tasks marked "未开始" that are already implemented
- `docs/issues.md` claims 2 P2 issues remain open, but all listed P2s are fixed
- `docs/issues.md` P3 "待规划功能" lists deregister/pause/resume as unplanned, yet they exist
- `docs/issues.md` implementation tables mark features as done that the prose section still calls pending

**What is genuinely missing**:
- Undo/rollback to a specific event point (P3-5)
- Hierarchical requirement deltas (scenario B)
- Multi-human review voting (scenario E)
- Cross-session comparison (scenario C)
- Constant externalization not 100% complete

---

## Key Gaps

1. **Documentation lying** — spec and issues.md lag behind code reality, eroding trust
2. **Test surface** — 37 tests for ~200KLOC of source; critical paths (consensus, human_review, phase transitions) under-tested
3. **CLARIFY_REWRITE auto-advance** — spec lists as unstarted; needs verification if logic is actually correct
4. **No undo** — once a vote or decision is submitted, it cannot be reverted; blocks real-world usability
5. **Requirement deltas are flat** — cannot attach child requirements to parent requirements

---

## Recommended Focus

Stabilize the **usable product surface** before expanding into new scenarios.

Priority order:
1. Fix documentation drift so the team trusts the plan
2. Verify and fix any hidden bugs in the clarification auto-advance logic
3. Add undo/rollback (the biggest usability gap)
4. Increase test coverage on consensus and phase-transition paths
5. Complete constant externalization
6. Add hierarchical requirement deltas (small scope, high user value)

---

## Ordered Work Queue (5–10 Loops)

| Loop | Type | Task | Why |
|------|------|------|-----|
| 1 | docs sync | Audit `specification.md` task statuses against code; flip finished items to ✅ | Documentation lying erodes planning trust |
| 2 | docs sync | Fix `issues.md` P2 count, sync P3 prose with implementation tables, update README if needed | Same as above |
| 3 | bugfix | Verify `CLARIFY_REWRITE` auto-advance in `engine.py`; fix if it does not auto-advance after all agents submit refined requirements | Spec claims unstarted; could be a real gap |
| 4 | test improvement | Add tests for consensus deadlock paths, ABSTAIN handling, human_reject round reset | High-risk logic, currently shallow coverage |
| 5 | feature completion | Implement basic undo: `revert_to_event(session_id, event_id)` using existing event log | Biggest real usability gap |
| 6 | API behavior | Audit `web.py` endpoints against `specification.md`; add any missing REST routes already defined in spec | API surface completeness |
| 7 | small refactor | Finish constant externalization (`AGENT_INACTIVE_TIMEOUT_SECONDS`, `CLARITY_THRESHOLD`, etc.) from `models.py` to env vars | Configurability debt |
| 8 | state/data | Extend `add_requirement_delta` to support `parent_delta_id` for hierarchical requirements | Scenario B, small scope |
| 9 | test improvement | Add E2E API test skeleton (pytest + httpx) covering create-session → register-agent → submit-proposal → consensus | Catches integration drift |
| 10 | docs sync | Final sweep: README, spec, issues.md aligned; mark phase complete | Closure signal |

---

## What NOT to Work On

- **No SQLite backend perfection** — it works; full transaction/migration polish is over-engineering for current stage
- **No multi-format export** — PDF/HTML/DOCX is speculative; Markdown is sufficient
- **No frontend redesign** — Web UI is functional; visual polish is low ROI
- **No cross-session comparison** — high complexity, low immediate user signal
- **No multi-human review voting** — depends on undo/rollback first; defer until event-reversion is solid
- **No large refactor** — engine.py is large but stable; resist temptation

---

## Success Signal for Ending This Phase

This phase ends when **all of the following** are true:

1. `docs/specification.md`, `docs/issues.md`, and `README.md` accurately reflect code reality
2. `CLARIFY_REWRITE` auto-advance behavior is verified correct (or fixed)
3. Undo/rollback to a specific event is implemented and tested
4. At least 3 new integration-level tests exist for consensus and phase transitions
5. No documented P1/P2 issues remain unaddressed
6. Test count ≥ 50 (from current 37)

Then: enter **scenario expansion phase** (hierarchical requirements, multi-human review, cross-session comparison).
