# Project Rules

## Project Runtime Facts

- **Name**: DesignDoc MCP (designdoc-mcp)
- **Version**: 0.3.0
- **Language**: Python >= 3.10 (from pyproject.toml)
- **Framework**: FastMCP + FastAPI (from pyproject.toml dependencies and README)
- **Build**: hatchling (from pyproject.toml)
- **Test Runner**: pytest with pytest-asyncio (from pyproject.toml)
- **Linter**: ruff (from pyproject.toml)

## Directory Structure

- `src/designdoc_mcp/` — main source package
- `tests/` — test suite
- `docs/` — documentation
- `data/` — runtime data directory
- `configs/` — client reference configurations

## Protocol Operating Rules

- `/dev-init` has been run. State files exist in `.agents/dev-protocol/`.
- `checkpoint.last_commit` is intentionally empty until first `/dev-save`.
- `phase` is `unknown` until set by user or `/dev-status`.
- Do NOT infer project architecture from source code during init.
- Do NOT auto-commit protocol state changes.

## Unknown / Requires Validation

- Storage backend details (SQLite vs JSON) — not explicitly documented in README
- Architecture depth (event sourcing, debate engine internals) — requires `/dev-status` or `/dev-scope`
- Current development priority (requires `/dev-scope`)
- Whether any outstanding bugs exist beyond docs/issues.md
