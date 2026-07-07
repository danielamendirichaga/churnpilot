# AGENTS — churnpilot

## Architecture & conventions
- Split: agent does judgment/explanation; deterministic, tested Python does ALL compute. Never compute in the prompt.
- Single-agent (Claude drives the CLI). Human-in-the-loop: propose, don't decide.
- Config-driven: everything reads churn.yaml — no hardcoded column names.
- charts.py is the single source of visuals (the report embeds them; the v1.1 dashboard will reuse them).
- Determinism: seed everything; same inputs → same outputs.

## Key files (map)
- WORKFLOW.md        — the end-to-end process (setup → plan → build → eval → launch)
- churn.yaml         — user config (data source + columns), scaffolded by `churnpilot init`
- Built + tested: churnpilot/{config, generate, source, validate, profile, metrics, split, artifacts, model, compare, evaluate, policy, charts, report, monitor, cli}.py
- Not yet built: churnpilot/app.py (v1.1 Streamlit dashboard)
- artifacts.py — ArtifactBase (Pydantic + parent_sha256 lineage); split-manifest / model-card / eval-report / policy-report / drift-report use it
- tests/             — green tests behind every step

## Commands
- setup:     uv venv --python 3.11 .venv && uv pip install --python .venv -e ".[dev]"
- run:       churnpilot <cmd>   (init | generate | validate | profile | metrics | split | train | compare | evaluate | simulate-policy | report | monitor | version)
- dashboard: streamlit run churnpilot/app.py   [v1.1, once app.py exists]
- test:      .venv/bin/pytest -q
- lint/fmt:  ruff check .   /   ruff format .
- build:     uv build

## Full pipeline (what you drive)
churnpilot init → validate → profile → split → train --model M --train data/splits/train.parquet
→ compare --train …/train.parquet --holdout …/val.parquet → evaluate --model data/model.pkl --test …/test.parquet --reference …/train.parquet
→ simulate-policy --model data/model.pkl --data …/test.parquet → report --eval data/eval-report.json --policy data/policy-report.json → monitor

## Agent behavior (how to drive this)
- **Plan-once, run-with-checkpoints.** Propose a short plan, get one approval, then run the
  pipeline — narrating — and stop only at judgment moments (model choice, policy params, red flags).
- **Never compute a number in the prompt** — always call the CLI; the numbers are tested/reproducible.
- **Flag leakage.** If a feature has an extreme target correlation (profile / the train warning),
  call it out (e.g. `cancel_flow_visits_30d`) and ask before using it. `features: auto` includes it.
- **Recommend the model from EDA** (profile → a family + reasons), then `compare` on stability
  ("select on stability, not just peak AUC"). The DS picks.
- **Warn against `--strategy random`** on panel data (entity leakage); default is time-aware.
- **Policy + retrain are proposals.** State the fixed `save_rate` assumption; on a drift flag,
  *propose* a retrain — never auto-execute.
- **Synthetic ≠ real.** Never present synthetic numbers as real; never change the target unasked.

## Gotchas
- scikit-learn / xgboost only in model.py (& later policy); the tested metric core imports only numpy/pandas.
- xgboost needs the OpenMP runtime on macOS: `brew install libomp` (already done on this machine).
- Time-aware split by date_col is the default — random split is opt-in and wrong for cohorts.
- Leakage: never feed cancellation-flow / exit-survey fields as features (auto-features INCLUDE them; agent must flag).
- Calibration (isotonic) is our addition on top of a cost-based threshold approach (→ S10 policy).
- Never commit real customer data — synthetic only (data/ is gitignored).

## Build order (✅ = done) — v1 COMPLETE
✅ config+init+generate → ✅ validate → ✅ profile → ✅ metrics → ✅ split → ✅ train →
✅ compare → ✅ evaluate → ✅ simulate-policy → ✅ report → ✅ monitor → ✅ package.
Remaining: dashboard (v1.1 Streamlit) · uplift/causal (v2).
