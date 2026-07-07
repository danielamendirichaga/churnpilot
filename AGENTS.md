# AGENTS — churnpilot

## Architecture & conventions
- Split: agent does judgment/explanation; deterministic, tested Python does ALL compute. Never compute in the prompt.
- Single-agent (Claude drives the CLI). Human-in-the-loop: propose, don't decide.
- Config-driven: everything reads churn.yaml — no hardcoded column names.
- charts.py will be the single source of visuals (report + dashboard reuse it) — not built yet.
- Determinism: seed everything; same inputs → same outputs.

## Key files (map)
- WORKFLOW.md        — the end-to-end process (setup → plan → build → eval → launch)
- churn.yaml         — user config (data source + columns), scaffolded by `churnpilot init`
- Built + tested: churnpilot/{config, generate, source, validate, profile, metrics, split, artifacts, model, cli}.py
- Not yet built (per build order): churnpilot/{compare, evaluate, policy, monitor, charts, report, app}.py
- artifacts.py — ArtifactBase (Pydantic + parent_sha256 lineage); split-manifest & model-card use it
- tests/             — green tests behind every step

## Commands
- setup:     uv venv --python 3.11 .venv && uv pip install --python .venv -e ".[dev]"
- run:       churnpilot <command>   (version | init | generate | validate | profile | metrics | split | train)
- dashboard: streamlit run churnpilot/app.py   [once app.py exists]
- test:      .venv/bin/pytest -q
- lint/fmt:  ruff check .   /   ruff format .
- build:     uv build

## Gotchas
- scikit-learn / xgboost only in model.py (& later policy); the tested metric core imports only numpy/pandas.
- xgboost needs the OpenMP runtime on macOS: `brew install libomp` (already done on this machine).
- Time-aware split by date_col is the default — random split is opt-in and wrong for cohorts.
- Leakage: never feed cancellation-flow / exit-survey fields as features (auto-features INCLUDE them; agent must flag).
- Calibration (isotonic) is our addition on top of a cost-based threshold approach (→ S10 policy).
- Never commit real customer data — synthetic only (data/ is gitignored).

## Build order (✅ = done)
✅ config+init+generate → ✅ validate → ✅ profile → ✅ metrics → ✅ split → ✅ train →
compare → evaluate → simulate-policy → report → monitor → package → dashboard (v1.1).
