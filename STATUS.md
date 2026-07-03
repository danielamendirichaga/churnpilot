# Status — churnpilot (updated 2026-07-03)

## Done
- Setup complete: `churnpilot` package, `.venv` (Python 3.11.15), deps installed, verified green (`pytest` + `churnpilot version`).
- Private GitHub repo `danielamendirichaga/churnpilot` created + pushed (main tracks origin/main).
- **Planning — grilling complete.** Full design pressure-tested against prior work + established practice (`local-notes/`). All decisions captured in **`docs/DESIGN_BRIEF.md`**.

## In progress
- Planning §2.2 — turning the design brief into the PRD.

## Next up
1. `/to-prd` — generate `PRD.md` (three layers: ML engine / contract / agent behavior) + `context.md` + ADRs + user stories + slice breakdown, from `docs/DESIGN_BRIEF.md`.
2. `/to-issue` — one GitHub issue per slice.
3. Build slice 1: `config` + `init` + `generate` (synthetic Netflix-style panel).

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
