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
- Status: pending

## Loop 3 — Add multi-human review voting foundation

- Files: `src/designdoc_mcp/engine.py`, `src/designdoc_mcp/models.py`, `tests/test_engine.py`
- Goal: Support multiple human reviewers with vote aggregation (agree/disagree/abstain)
- Validation: `test_multi_human_votes` passes; multiple votes aggregated correctly
- Status: pending
