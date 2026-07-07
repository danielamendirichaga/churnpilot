# churnpilot

**A config-driven churn/retention analysis copilot: the AI does the judgment, a deterministic,
unit-tested Python CLI does the compute, and typed artifacts with lineage are the contract
between them.**

Point it at a customer table (via one `churn.yaml`) and an AI agent drives a reproducible
pipeline to predict who will churn, decide who to save under a budget, and watch for drift —
proposing and explaining every step while the data scientist stays in charge.

> **Status: v1 complete.** The full pipeline — *generate → validate → profile → metrics →
> split → train → compare → evaluate → simulate-policy → report → monitor* — is built and
> tested (118 passing tests). Next: an interactive Streamlit dashboard (v1.1) and uplift/causal
> modeling (v2). See [STATUS.md](STATUS.md) and [CHANGELOG.md](CHANGELOG.md).

---

## The idea

Churn work is easy to get **wrong-but-confident** — a model that looks great in-sample quietly
collapses in production (data leakage, drift, an unstable score). churnpilot splits the job so
that never happens silently:

```
        ┌──────────────────────────┐        ┌───────────────────────────────┐
        │   AGENT (the LLM)         │        │   CLI (deterministic Python)  │
        │ • explores & interprets   │ calls  │ • generate / split / fit /    │
        │ • flags leakage & drift   │ ─────► │   score / measure             │
        │ • recommends & explains   │        │ • same input → same output    │
        │ • the DS decides          │ ◄───── │ • unit-tested, seeded         │
        └──────────────────────────┘ reads  └───────────────────────────────┘
                     │      typed artifacts (schema + parent_sha256 lineage)   ▲
                     └─────────────────────────────────────────────────────────┘
```

- **The agent** handles judgment — reading the data, flagging the leakage feature, recommending
  a model, narrating results.
- **The tested CLI** owns every number — you can't unit-test a vibe, but you *can* unit-test
  `psi(identical) == 0`. Same input → same output, always.
- **Typed artifacts with lineage** connect the steps, so you can always answer *"what data
  produced this model?"*

---

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv -e ".[dev]"
.venv/bin/pytest -q                        # 118 tests, green

# the full pipeline (synthetic data by default — no real data needed)
churnpilot init                            # write churn.yaml
churnpilot validate                        # is the data usable? (fails gracefully)
churnpilot profile                         # per-column EDA + a leakage hint
churnpilot split --strategy time           # out-of-time split, leakage-guarded
churnpilot train --model xgboost --train data/splits/train.parquet
churnpilot compare --train data/splits/train.parquet --holdout data/splits/val.parquet
churnpilot evaluate --model data/model.pkl --test data/splits/test.parquet --reference data/splits/train.parquet
churnpilot simulate-policy --model data/model.pkl --data data/splits/test.parquet --budget 5000
churnpilot report --eval data/eval-report.json --policy data/policy-report.json   # → data/report.html
churnpilot monitor                         # per-feature drift + retrain verdict
```

Materialize the synthetic dataset to a file with `churnpilot generate --out data/panel.parquet`,
then point `churn.yaml` at your own data (`source: {kind: file, path: ...}` — or postgres/sqlite).
*(macOS: XGBoost needs `brew install libomp`.)*

---

## What's inside (highlights)

- **Clean-room, tested metric core** (numpy/pandas only) — decile-table KS, PSI with frozen
  reference edges, rank-order-breaks, gain/lift, ROC/PR-AUC, log-loss, calibration — all
  hand-implemented and unit-tested.
- **Leakage, made teachable** — a *planted* leakage feature the profiler flags at +0.92
  correlation, and a **leakage-guarded split** whose "random" mode *detects* the classic
  panel-data entity leak instead of hiding it (time-aware is the default).
- **A model menu** — L1 logistic, pruned decision tree, random forest, XGBoost — in a
  leakage-safe pipeline (fit on train only), with an always-on baseline floor and optional
  SMOTE, isotonic calibration, and (mode-aware) early stopping.
- **Typed artifacts** — `split-manifest`, `model-card` — Pydantic-validated with content-hash
  (`parent_sha256`) lineage.
- **Config-driven** — works on any churn dataset, panel *or* single-snapshot, from one
  `churn.yaml`; drift/time features degrade gracefully when there's no date column.

---

## Docs

- **[WORKFLOW.md](WORKFLOW.md)** — the build process (plan → slice → verify → commit).
- **[docs/DESIGN_BRIEF.md](docs/DESIGN_BRIEF.md)** — every design decision.
- **[docs/PRD.md](docs/PRD.md)** — requirements + the 13-slice build plan.
- **[docs/ADRs.md](docs/ADRs.md)** — architecture decision records.
- **[docs/synthetic-data.md](docs/synthetic-data.md)** — the synthetic dataset spec.
- **[AGENTS.md](AGENTS.md)** — how the code is organized.

---

## Provenance

- **Original / clean-room.** All code is written from scratch, reimplementing standard, public
  methods (decile-table KS, PSI, leakage-safe pipelines) — nothing is copied from any source.
- **Synthetic data only.** Everything under `data/` is generated by `churnpilot generate` from a
  seed. No real customer data, no PII.
- **Original design.** The architecture (AI judgment + a tested CLI + typed artifacts) and the
  streaming-subscription domain are churnpilot's own.

## License

[MIT](LICENSE).
