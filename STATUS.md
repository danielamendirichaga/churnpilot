# Status — churnpilot (updated 2026-07-02)

## Done
- Setup complete. Package `churnpilot` scaffolded; `pyproject.toml`, `.gitignore`, `README.md`.
- Environment: `uv` installed; `.venv` (Python 3.11.15) created; deps installed (`-e ".[dev]"`).
- Verified GREEN: `pytest` (1 passed) + `churnpilot version` → 0.1.0 + `--help` lists commands.
- CLI: added a Typer callback so subcommands work while only one command exists.
- Keystone files current: `WORKFLOW.md`, `AGENTS.md`, `STATUS.md`, `CHANGELOG.md`.
- Git: initial commit; private GitHub repo `danielamendirichaga/churnpilot` created and pushed.

## In progress
- Nothing — Setup done.

## Next up
Planning (WORKFLOW §2):
1. Capture the raw idea (one paragraph).
2. `/grill-with-docs` — pressure-test the idea against the prior work docs.
3. Domain modeling — Customer, Cohort, Score, Model, Policy, Offer, DriftReport.
4. `/to-prd` — the layered PRD (ML engine / contract / agent behavior) → slice breakdown.
5. `/to-issue` — one GitHub issue per slice.
Then Build slice 1: config + init + generate.

## Blockers / open questions
- None.
