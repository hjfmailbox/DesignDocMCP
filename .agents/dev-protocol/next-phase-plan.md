# Next Phase Plan

> Generated after documentation sync completion (Loops 1-17 done).
> Previous plan archived in git history at commit `f96c225`.

## Loop 1 — Fix revert_to_event delta truncation

**Status:** completed

**Goal:** Extend `revert_to_event()` to also truncate `session.requirement_deltas` based on `created_at <= target_event.created_at`, preventing inconsistent requirement hierarchy after undo.

**Files:** `src/designdoc_mcp/engine.py`, `tests/test_engine.py`

**Validation:**
- New regression test `test_revert_truncates_deltas` passes
- All 66 existing tests pass
- `revert_to_event` leaves no deltas newer than the target event

---

## Loop 2 — Standardize API error HTTP status codes

**Status:** completed

**Goal:** Change invalid-session and validation-failure responses from `200 + {"error":"..."}` to proper HTTP status codes (`404 Not Found`, `400 Bad Request`).

**Files:** `src/designdoc_mcp/web.py`, `tests/test_api_e2e.py`

**Validation:**
- E2E tests updated to expect 404/400 instead of 200+error body
- All tests pass
- No remaining endpoints return 200 for client-error cases

---

## Loop 3 — Expose RequirementDelta hierarchy in session APIs

**Status:** completed

**Goal:** Make `RequirementDelta` parent-child relations visible in `get_session_summary()` and `get_session_flow()` so the requirement evolution tree can be inspected.

**Files:** `src/designdoc_mcp/engine.py`, `src/designdoc_mcp/models.py`

**Validation:**
- API responses include `delta_count`, `delta_tree`, or `parent_delta_id` fields
- Tests verify hierarchy structure is correctly serialized
- All existing tests pass

---

## Loop 4 — Expand E2E API coverage for debate and undo flows

**Status:** completed

**Goal:** Add E2E test suites covering multi-agent disagreement paths, undo lifecycle, and agent reconnect flows.

**Files:** `tests/test_api_e2e.py`

**Validation:**
- New E2E suites for `proposal → challenge → vote → review`, `undo lifecycle`, `agent reconnect` pass
- Test count increases from 66
- No regressions in existing tests

---

## Loop 5 — Add JSON export format support

**Status:** pending

**Goal:** Extend document generation with a structured JSON export alongside existing Markdown and HTML.

**Files:** `src/designdoc_mcp/document.py`, `src/designdoc_mcp/server.py`

**Validation:**
- New `generate_design_document_json` MCP tool registered and callable
- JSON output contains structured session data (requirements, decisions, agents)
- Test passes; behavior consistent with Markdown/HTML export patterns
