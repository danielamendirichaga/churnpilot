# Status — churnpilot (updated 2026-07-07)

## Done
- Setup complete: `churnpilot` package, `.venv` (Python 3.11.15), deps installed, verified green (`pytest` + `churnpilot version`).
- Private GitHub repo `danielamendirichaga/churnpilot` created + pushed (main tracks origin/main).
- **Planning — grilling complete.** Full design pressure-tested against the prior work reference and established ML practice. All decisions in **`docs/DESIGN_BRIEF.md`**.
- **Planning — PRD complete.** `docs/context.md`, `docs/ADRs.md` (10 ADRs), `docs/PRD.md` (3 layers, 12 user stories, functional requirements, 13-slice v1 breakdown with traceability).
- **GitHub issues #1–#13 created** (one per slice S1–S13, label `v1-slice`).
- **S1 (#1) — Config + `init` — DONE.** `churn.yaml` Pydantic schema (`ChurnConfig`/`SourceConfig`/`ColumnMap`), `load_config` (graceful `ConfigError`), `init` command + template. Added `pydantic`/`types-PyYAML` deps + `[tool.mypy]` (pydantic plugin). Verified: ruff + mypy clean, 14 tests green, `churnpilot init` round-trips.
- **S2 (#2) — `generate` — DONE.** Deterministic synthetic streaming panel (`churnpilot/generate.py` `make_panel`); 25-col schema + 4 levers (drift/imbalance/missingness/leakage trap) + cltv; `generate` CLI writes parquet + summary. Verified: ruff + mypy clean, 23 tests green; full run 8k×24 = 59,683 rows, churn 0.100, ~1s. Spec: `docs/synthetic-data.md`.
- **S3 (#3) — `source` + `validate` — DONE.** `source.py` `load_data` (synthetic/file[parquet,csv]/sqlite tested; postgres path present). `validate.py` `validate` → graded `ValidationReport` (✔/⚠/✗), panel-vs-snapshot mode, fails gracefully. `validate` CLI (loads config→data→report, non-zero exit on hard fail). Verified: ruff + mypy clean, 40 tests green; smoke on healthy + broken configs.
- **S4 (#4) — `profile` — DONE.** `profile.py` `profile_frame` (config-driven roles + null rate + cardinality + numeric stats + numeric-feature target_corr) and `high_corr_features` (leakage hint). `profile` CLI prints the EDA table + a `⚠ possible leakage` line. Shared `_load` helper in cli.py (validate+profile). Verified: ruff + mypy clean, 47 tests green; smoke flags `cancel_flow_visits_30d` at +0.92.
- **S5 (#5) — metric core + `metrics` — DONE.** `metrics.py` (numpy/pandas only): `ks_table`, `psi` (frozen edges), `rank_order_breaks`, `gain_table`/`top_decile_lift`, `roc_auc`, `average_precision` (PR-AUC), `precision_recall_f1`, `log_loss`, `calibration_table`/`expected_calibration_error`. `metrics` CLI (score-col vs target + optional reference PSI). Verified: ruff + mypy clean, 62 tests green; smoke — leakage feature 0.9998 AUC vs genuine driver 0.62.
- **S6 (#6) — `split` — DONE.** `artifacts.py` (**`ArtifactBase`** + `parent_sha256` lineage + `content_hash` + JSON sidecar — the contract layer). `split.py` `split_dataset` (time/grouped/random) + leakage guard + `SplitManifest`. `split` CLI writes 3 parquets + `split-manifest.json`. Verified: ruff + mypy clean, 71 tests green; smoke — time is time-ordered (1,334 legit overlap, ✔), random flags 4,822 entity leakage (⚠).
- **S7 (#7) — `train` — DONE (+amended).** `model.py`: menu (logistic L1 / pruned tree / rf / xgboost) in a leakage-safe `ColumnTransformer` pipeline (fit-on-train), optional SMOTE + isotonic calibration, always-on baseline floor; `ModelCard` artifact; joblib persist/load. A standard, leakage-safe stack. **Amendment:** XGBoost `--early-stopping` over a mode-aware inner-val (time-aware panel / stratified snapshot) + a train-time `⚠ leakage` warning. Added deps `xgboost`/`imbalanced-learn`/`joblib` + macOS `libomp`. Verified: ruff + mypy clean, 88 tests green. (Measured: early-stopping 0.662 vs fixed 0.655; time-vs-stratified inner-val negligible — kept time-aware on principle.)

## In progress
- Nothing.

## Active issue
- **#8 — S8: `compare`** (next to build).

## Next up
1. Build **S8 (#8): `compare`** — fit the shortlist and rank on held-out performance + stability (train→test drop, score-PSI). Reuses `model.py` + `metrics.py`.
2. Then S9 `evaluate` (#9), S10 `simulate-policy` (#10), … per `docs/PRD.md` §7.

## Key locked decisions (see docs/DESIGN_BRIEF.md for full detail)
- Domain: streaming monthly subscription; target `churn_next_30d` (binary, next-cycle).
- Data: **panel** (subscriber-month) + graceful single-snapshot support; synthetic "Netflix-style" generator; Telco/KKBox as real-data options.
- Models: menu (logistic/tree/RF/XGBoost), EDA-driven agent choice, baseline floor, `compare` on stability. Standard, defensible methods (leakage-safe pipelines, SMOTE, cost-based thresholds, calibration).
- Metrics: union pack; headline = top-decile lift + PR-AUC.
- Policy: `benefit(x)` cost/value, fixed `save_rate` (v1); **uplift = v2** (needs simulated A/B test).
- Contract layer: **medium** (5 Pydantic artifacts + lineage).
- Agent: single, plan-once-run-with-checkpoints, guardrails defined.
- Scope: v1 (full core loop incl. compare + monitor) · v1.1 (Streamlit dashboard) · v2 (uplift, seasonality).

## Blockers / open questions
- None.
