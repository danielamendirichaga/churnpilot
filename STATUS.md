# Status — churnpilot (updated 2026-07-07)

## Done
- Setup complete: `churnpilot` package, `.venv` (Python 3.11.15), deps installed, verified green (`pytest` + `churnpilot version`).
- Private GitHub repo `danielamendirichaga/churnpilot` created + pushed (main tracks origin/main).
- **Planning — grilling complete.** Full design pressure-tested against established ML and software practice. All decisions in **`docs/DESIGN_BRIEF.md`**.
- **Planning — PRD complete.** `docs/context.md`, `docs/ADRs.md` (10 ADRs), `docs/PRD.md` (3 layers, 12 user stories, functional requirements, 13-slice v1 breakdown with traceability).
- **GitHub issues #1–#13 created** (one per slice S1–S13, label `v1-slice`).
- **S1 (#1) — Config + `init` — DONE.** `churn.yaml` Pydantic schema (`ChurnConfig`/`SourceConfig`/`ColumnMap`), `load_config` (graceful `ConfigError`), `init` command + template. Added `pydantic`/`types-PyYAML` deps + `[tool.mypy]` (pydantic plugin). Verified: ruff + mypy clean, 14 tests green, `churnpilot init` round-trips.
- **S2 (#2) — `generate` — DONE.** Deterministic synthetic streaming panel (`churnpilot/generate.py` `make_panel`); 25-col schema + 4 levers (drift/imbalance/missingness/leakage trap) + cltv; `generate` CLI writes parquet + summary. Verified: ruff + mypy clean, 23 tests green; full run 8k×24 = 59,683 rows, churn 0.100, ~1s. Spec: `docs/synthetic-data.md`.
- **S3 (#3) — `source` + `validate` — DONE.** `source.py` `load_data` (synthetic/file[parquet,csv]/sqlite tested; postgres path present). `validate.py` `validate` → graded `ValidationReport` (✔/⚠/✗), panel-vs-snapshot mode, fails gracefully. `validate` CLI (loads config→data→report, non-zero exit on hard fail). Verified: ruff + mypy clean, 40 tests green; smoke on healthy + broken configs.
- **S4 (#4) — `profile` — DONE.** `profile.py` `profile_frame` (config-driven roles + null rate + cardinality + numeric stats + numeric-feature target_corr) and `high_corr_features` (leakage hint). `profile` CLI prints the EDA table + a `⚠ possible leakage` line. Shared `_load` helper in cli.py (validate+profile). Verified: ruff + mypy clean, 47 tests green; smoke flags `cancel_flow_visits_30d` at +0.92.
- **S5 (#5) — metric core + `metrics` — DONE.** `metrics.py` (numpy/pandas only): `ks_table`, `psi` (frozen edges), `rank_order_breaks`, `gain_table`/`top_decile_lift`, `roc_auc`, `average_precision` (PR-AUC), `precision_recall_f1`, `log_loss`, `calibration_table`/`expected_calibration_error`. `metrics` CLI (score-col vs target + optional reference PSI). Verified: ruff + mypy clean, 62 tests green; smoke — leakage feature 0.9998 AUC vs genuine driver 0.62.
- **S6 (#6) — `split` — DONE.** `artifacts.py` (**`ArtifactBase`** + `parent_sha256` lineage + `content_hash` + JSON sidecar — the contract layer). `split.py` `split_dataset` (time/grouped/random) + leakage guard + `SplitManifest`. `split` CLI writes 3 parquets + `split-manifest.json`. Verified: ruff + mypy clean, 71 tests green; smoke — time is time-ordered (1,334 legit overlap, ✔), random flags 4,822 entity leakage (⚠).
- **S7 (#7) — `train` — DONE (+amended).** `model.py`: menu (logistic L1 / pruned tree / rf / xgboost) in a leakage-safe `ColumnTransformer` pipeline (fit-on-train), optional SMOTE + isotonic calibration, always-on baseline floor; `ModelCard` artifact; joblib persist/load. A standard, leakage-safe stack. **Amendment:** XGBoost `--early-stopping` over a mode-aware inner-val (time-aware panel / stratified snapshot) + a train-time `⚠ leakage` warning. Added deps `xgboost`/`imbalanced-learn`/`joblib` + macOS `libomp`. Verified: ruff + mypy clean, 88 tests green. (Measured: early-stopping 0.662 vs fixed 0.655; time-vs-stratified inner-val negligible — kept time-aware on principle.)

- **S8 (#8) — `compare` — DONE.** `compare.py` `compare_models` — fits the shortlist on train, scores a holdout, ranks on held-out AUC/KS/lift/PR-AUC **and** stability (train→holdout auc/ks drop, score-PSI) + a `stable` gate flag. `compare` CLI prints the ranked table + names best + most-stable. Reuses `model.py`/`metrics.py`. Verified: ruff + mypy clean, 93 tests green; smoke — L1 logistic best (0.675) *and* most stable (drop +0.012) while rf/xgboost overfit (drop +0.23/+0.16).

- **S9 (#9) — `evaluate` — DONE.** `evaluate.py` `evaluate_model` — scores held-out data, reports the union metric pack (AUC/PR-AUC/KS/rank-order/lift + precision/recall/F1/log-loss/ECE), per-segment slices (plan_tier/region), and optional score-PSI vs a reference; emits `EvalReport` artifact (lineage). `evaluate` CLI. Verified: ruff + mypy clean, 98 tests green; smoke — test AUC 0.655, ECE 0.013, PSI 0.027, Premium AUC 0.690 vs Standard 0.638.

- **S10 (#10) — `simulate-policy` — DONE.** `policy.py` `simulate_policy` — scores customers, ranks by `benefit(x)=save_rate·P(churn)·CLTV − offer_cost`, targets the positive-benefit set under a budget (`--budget $` or `--n-offers`), reports retained value / spend / net / ROI + a trade-off curve + by-segment; emits `PolicyReport` artifact. Requires `value_col`. Verified: ruff + mypy clean, 106 tests green; smoke — $2k budget → 666 targeted, ROI 6.15×; unlimited → net $32,767, ROI 2.37×.

- **S11 (#11) — `charts` + `report` — DONE.** `charts.py` — one tested source of visuals (validated **clean-light** palette): gain/lift, calibration, per-segment lift, policy trade-off (each → PNG bytes). `report.py` `build_html` assembles a self-contained `report.html` (stat tiles + charts embedded base64) from the `eval-report`/`policy-report`/`model-card` artifacts. `report` CLI. Enriched `EvalReport` with a `gain` table. Verified: ruff + mypy clean, 111 tests green; smoke — 248 KB self-contained report, 4 charts; design signed off.

- **S12 (#12) — `monitor` — DONE.** `monitor.py` `monitor_drift` — per-feature PSI earliest→latest cohort, `major`/`moderate`/`stable` status, retrain-recommended flag; graceful snapshot skip; emits `DriftReport` artifact. `monitor` CLI. Verified: ruff + mypy clean, 117 tests green; smoke — `watch_hours_30d` PSI 0.72 tops the list, 7 features flagged, retrain recommended (DS-leads).
- **S13 (#13) — agent wiring + package — DONE. 🎉 v1 COMPLETE.** Finalized `AGENTS.md` (full command map + agent-behavior/guardrails + full-pipeline recipe). Capstone `tests/test_pipeline.py` runs the whole pipeline (generate→…→monitor) + all 5 artifacts. `uv build` → wheel; verified clean `pip install` of the wheel in a fresh venv → `churnpilot version`/`init`/`validate` work. README quickstart extended to the full pipeline. 118 tests green.

### v2 — uplift / causal
- **S14 (#14) — generator treatment simulation — DONE.** `make_panel(treatment=True)` overlays a randomized A/B test: balanced `treated`, heterogeneous `τ(x)` (`_uplift_tau`) spanning all 4 quadrants incl. sleeping dogs (τ<0), monotone-coupled potential outcomes → observed churn = factual; oracle cols (`true_uplift`/counterfactuals) for honest Qini. `feature_columns` guards oracle+`treated` from leaking. `generate --treatment` CLI. Verified: ruff + mypy clean, 126 tests green (v1 untouched); smoke 8k×24 → treated 0.498, ATE +0.037, 8% sleeping dogs.
- **S15 (#15) — uplift models — DONE.** `uplift.py`: S-learner (treated as feature) + T-learner (two models) over `model.py`; `predict_uplift` = churn-prob reduction; `UpliftCard` (+ τ-recovery corr vs synthetic truth); `train-uplift` CLI + joblib persist. Verified: ruff + mypy clean, 133 tests green; smoke 66k rows → **T-learner recovery corr +0.40 vs S-learner +0.14** (both match ATE; T-learner captures heterogeneity, S-learner shrinks it — the known result).

## In progress
- Nothing — **v1 shipped.**

## Active track
- **v2 — uplift / causal (BUILDING).** Design **accepted** (`docs/v2-design-brief.md`); issues **#14–#18** created (`v2-slice`). v1.1 dashboard deferred.

## Active issue
- **#16 — S16: Qini / uplift evaluation** (next to build).

## Next up (v2)
1. **S16 (#16)** — `qini.py`: Qini curve + coefficient + uplift-by-decile + true-vs-estimated τ; `QiniReport`; `uplift-eval` CLI. (No course reference — uplift/causal not covered here; standard causal-ML.)
2. Then S17 uplift policy + risk-vs-uplift contrast → S18 report + docs + v2 capstone.
3. *(Optional)* pre-public **history cleanup** (see standing constraints in memory).

## Deferred
- **v1.1 — Streamlit `dashboard`** (`churnpilot/app.py`): interactive policy sliders over `charts.py`. Dropped for now in favor of v2; revisit after.

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
