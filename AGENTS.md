# AGENTS — churnpilot

## Architecture & conventions
- Split: agent does judgment/explanation; deterministic, tested Python does ALL compute. Never compute in the prompt.
- Single-agent (Claude drives the CLI). Human-in-the-loop: propose, don't decide.
- Config-driven: everything reads churn.yaml — no hardcoded column names.
- charts.py is the single source of truth for visuals (report + dashboard reuse it).
- Determinism: seed everything; same inputs → same outputs.

## Key files (map)
- WORKFLOW.md        — the end-to-end process (setup → plan → build → eval → launch)
- churn.yaml         — user config (data source + columns)  [added in build slice 1]
- churnpilot/config.py, source.py, cli.py — present (config/source are skeletons)
- churnpilot/validate.py, metrics.py, model.py, policy.py, monitor.py, charts.py, report.py, app.py — added per build slice
- tests/             — green tests behind every step

## Commands
- setup:     uv venv --python 3.11 .venv && uv pip install --python .venv -e ".[dev]"
- run:       churnpilot <command>   (currently: version)
- dashboard: streamlit run churnpilot/app.py   [once app.py exists]
- test:      .venv/bin/pytest -q
- lint/fmt:  ruff check .   /   ruff format .
- build:     uv build

## Gotchas
- scikit-learn only in model/policy paths; tested core must import without it.
- Time-aware split by date_col is the default — random split is opt-in and wrong for cohorts.
- Leakage: never feed cancellation-flow / exit-survey fields as features.
- Never commit real customer data — synthetic only (data/ is gitignored).

## Build order
config+init+generate → validate → profile+metrics → split → train → evaluate →
simulate-policy → monitor → charts+report → app+dashboard → package.
