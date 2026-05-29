# Next Phase Plan

## Loop 1 — Implement compare_sessions MCP tool

- Files: `src/designdoc_mcp/server.py`, `src/designdoc_mcp/engine.py`, `tests/test_engine.py`
- Goal: Add cross-session comparison tool that returns structural diff of requirements, agents, and decisions
- Validation: `test_compare_sessions` passes; tool is registered and callable
- Status: completed

## Loop 2 — Add HTML export format support

- Files: `src/designdoc_mcp/document.py`, `src/designdoc_mcp/server.py`, `tests/test_engine.py`
- Goal: Generate HTML format design documents alongside Markdown
- Validation: `test_html_export` passes; HTML output contains session title and architecture
- Status: completed

## Loop 3 — Add multi-human review voting foundation

- Files: `src/designdoc_mcp/engine.py`, `src/designdoc_mcp/models.py`, `tests/test_engine.py`
- Goal: Support multiple human reviewers with vote aggregation (agree/disagree/abstain)
- Validation: `test_multi_human_votes` passes; multiple votes aggregated correctly
- Status: completed

## Loop 4 — Sync issues.md v1.3 and scenario statuses

- Files: `docs/issues.md`
- Goal: Mark compare_sessions, HTML export, and multi-human review as completed in v1.3 table and scenario sections; update P3-3 multi-format export to reflect HTML is done
- Validation: grep confirms no "📋 待规划" maps to already-implemented features
- Status: completed

## Loop 5 — Sync current-focus.md metrics and focus

- Files: `docs/current-focus.md`
- Goal: Update test count 56→66, add external validation loops 11-13 completion record, update focus to reflect reality
- Validation: current-focus.md content matches latest git reality
- Status: completed

## Loop 6 — Sync specification.md phase-5 tool list

- Files: `docs/specification.md`
- Goal: Add compare_sessions, generate_design_document_html, and submit_human_vote to the MCP tool / capability list
- Validation: specification.md lists all implemented MCP tools and document outputs
- Status: completed

## Loop 7 — Sync next-phase-plan.md missing list

- Files: `docs/next-phase-plan.md`
- Goal: Remove implemented features from "genuinely missing" and "What NOT to Work On"; update Current Reality Snapshot test count and capabilities
- Validation: "missing" list only contains truly unimplemented features (PDF/DOCX export, deterministic replay)
- Status: completed
