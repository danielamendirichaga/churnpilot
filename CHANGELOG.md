# Changelog — churnpilot

## 2026-07-02 — Project setup
- Scaffolded `churnpilot` package (CLI with `version` + Typer callback; `config`/`source` skeletons) and `tests/` (smoke test).
- Added `pyproject.toml` (hatchling, typer entry point, dev extras), `README.md`, `.gitignore`.
- Created keystone files: `WORKFLOW.md`, `AGENTS.md`, `STATUS.md`, `CHANGELOG.md`.
- Environment: installed `uv`; created `.venv` (Python 3.11.15); installed deps (`-e ".[dev]"`).
- Verified green: `pytest` (1 passed), `churnpilot version` (0.1.0), `churnpilot --help`.
- Initialized git; created private GitHub repo `danielamendirichaga/churnpilot` and pushed the initial commit.

## 2026-07-03 — Planning: design brief (grilling complete)
- Ran a full grilling session; pressure-tested the design against prior work and reference materials (`local-notes/`).
- Captured every decision in `docs/DESIGN_BRIEF.md` (domain, panel data model, synthetic generator spec, split/leakage, model menu + EDA-driven choice, metrics, cost-based policy, medium contract layer, agent behavior, v1/v1.1/v2 scope).
- Next: `/to-prd` from the design brief.

## 2026-07-03 — Planning: PRD
- Produced `docs/context.md` (background/constraints/non-goals), `docs/ADRs.md` (10 architecture decision records), and `docs/PRD.md`.
- PRD structured in the three layers (ML engine / contract / agent behavior) with functional requirements, 12 user stories + acceptance criteria (tagged by test layer), and a 13-slice v1 build plan with requirement→slice traceability.
- Next: `/to-issue` (one issue per slice) → build S1 (config + init).

## 2026-07-07 — S1: config + init (#1)
- `churnpilot/config.py`: Pydantic `churn.yaml` schema (`ChurnConfig` / `SourceConfig` / `ColumnMap`, `extra="forbid"`), `load_config` raising a readable `ConfigError`, and the `CONFIG_TEMPLATE`.
- `churnpilot/cli.py`: `init` command scaffolds `churn.yaml` (won't overwrite without `--force`).
- Added deps `pydantic`, `types-PyYAML`; added `[tool.mypy]` (python 3.11 + pydantic plugin).
- `tests/test_config.py`: 12 tests (valid/default/error paths + `init` round-trip). Full suite 14 green; ruff + mypy clean. (Closes #1)
