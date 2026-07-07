# Status — churnpilot (updated 2026-07-03)

## Done
- Setup complete: `churnpilot` package, `.venv` (Python 3.11.15), deps installed, verified green (`pytest` + `churnpilot version`).
- Private GitHub repo `danielamendirichaga/churnpilot` created + pushed (main tracks origin/main).
- **Planning — grilling complete.** Full design pressure-tested against prior work + established practice (`local-notes/`). All decisions in **`docs/DESIGN_BRIEF.md`**.
- **Planning — PRD complete.** `docs/context.md`, `docs/ADRs.md` (10 ADRs), `docs/PRD.md` (3 layers, 12 user stories, functional requirements, 13-slice v1 breakdown with traceability).
- **GitHub issues #1–#13 created** (one per slice S1–S13, label `v1-slice`).
- **S1 (#1) — Config + `init` — DONE.** `churn.yaml` Pydantic schema (`ChurnConfig`/`SourceConfig`/`ColumnMap`), `load_config` (graceful `ConfigError`), `init` command + template. Added `pydantic`/`types-PyYAML` deps + `[tool.mypy]` (pydantic plugin). Verified: ruff + mypy clean, 14 tests green, `churnpilot init` round-trips.
- **S2 (#2) — `generate` — DONE.** Deterministic synthetic streaming panel (`churnpilot/generate.py` `make_panel`); 25-col schema + 4 levers (drift/imbalance/missingness/leakage trap) + cltv; `generate` CLI writes parquet + summary. Verified: ruff + mypy clean, 23 tests green; full run 8k×24 = 59,683 rows, churn 0.100, ~1s. Spec: `docs/synthetic-data.md`.

## In progress
- Nothing.

## Active issue
- **#3 — S3: `source` + `validate`** (next to build).

## Next up
1. Build **S3 (#3): `source` + `validate`** — unified loader (db/file/synthetic) + graceful validation report.
2. Then S4 `profile` (#4), S5 metric core (#5), … per `docs/PRD.md` §7.

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
