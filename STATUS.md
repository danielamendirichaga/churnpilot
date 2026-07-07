# Status — churnpilot (updated 2026-07-03)

## Done
- Setup complete: `churnpilot` package, `.venv` (Python 3.11.15), deps installed, verified green (`pytest` + `churnpilot version`).
- Private GitHub repo `danielamendirichaga/churnpilot` created + pushed (main tracks origin/main).
- **Planning — grilling complete.** Full design pressure-tested against prior work + established practice (`local-notes/`). All decisions in **`docs/DESIGN_BRIEF.md`**.
- **Planning — PRD complete.** `docs/context.md`, `docs/ADRs.md` (10 ADRs), `docs/PRD.md` (3 layers, 12 user stories, functional requirements, 13-slice v1 breakdown with traceability).
- **GitHub issues #1–#13 created** (one per slice S1–S13, label `v1-slice`).
- **S1 (#1) — Config + `init` — DONE.** `churn.yaml` Pydantic schema (`ChurnConfig`/`SourceConfig`/`ColumnMap`), `load_config` (graceful `ConfigError`), `init` command + template. Added `pydantic`/`types-PyYAML` deps + `[tool.mypy]` (pydantic plugin). Verified: ruff + mypy clean, 14 tests green, `churnpilot init` round-trips.

## In progress
- Nothing.

## Active issue
- **#2 — S2: `generate`** (next to build).

## Next up
1. Build **S2 (#2): `generate`** — seeded synthetic Netflix-style panel (feature schema + 4 levers + cltv + leakage trap) + determinism test.
2. Then S3 `source`+`validate` (#3), S4 `profile` (#4), … per `docs/PRD.md` §7.

## Key locked decisions (see docs/DESIGN_BRIEF.md for full detail)
- Domain: streaming monthly subscription; target `churn_next_30d` (binary, next-cycle).
- Data: **panel** (subscriber-month) + graceful single-snapshot support; synthetic "Netflix-style" generator; Telco/KKBox as real-data options.
- Models: menu (logistic/tree/RF/XGBoost), EDA-driven agent choice, baseline floor, `compare` on stability. Course-grounded (leakage-safe pipelines, SMOTE, cost-based thresholds, calibration).
- Metrics: union pack; headline = top-decile lift + PR-AUC.
- Policy: `benefit(x)` cost/value, fixed `save_rate` (v1); **uplift = v2** (needs simulated A/B test).
- Contract layer: **medium** (5 Pydantic artifacts + lineage).
- Agent: single, plan-once-run-with-checkpoints, guardrails defined.
- Scope: v1 (full core loop incl. compare + monitor) · v1.1 (Streamlit dashboard) · v2 (uplift, seasonality).

## Blockers / open questions
- None. (pyproject to gain `xgboost` / `imbalanced-learn` / `pydantic` when those slices land.)
