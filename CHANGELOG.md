# Changelog — churnpilot

## 2026-07-02 — Project setup
- Scaffolded `churnpilot` package (CLI with `version` + Typer callback; `config`/`source` skeletons) and `tests/` (smoke test).
- Added `pyproject.toml` (hatchling, typer entry point, dev extras), `README.md`, `.gitignore`.
- Created keystone files: `WORKFLOW.md`, `AGENTS.md`, `STATUS.md`, `CHANGELOG.md`.
- Environment: installed `uv`; created `.venv` (Python 3.11.15); installed deps (`-e ".[dev]"`).
- Verified green: `pytest` (1 passed), `churnpilot version` (0.1.0), `churnpilot --help`.
- Initialized git; created private GitHub repo `danielamendirichaga/churnpilot` and pushed the initial commit.

## 2026-07-03 — Planning: design brief (grilling complete)
- Ran a full grilling session; pressure-tested the design against prior work and reference materials (`local-notes/`).
- Captured every decision in `docs/DESIGN_BRIEF.md` (domain, panel data model, synthetic generator spec, split/leakage, model menu + EDA-driven choice, metrics, cost-based policy, medium contract layer, agent behavior, v1/v1.1/v2 scope).
- Next: `/to-prd` from the design brief.

## 2026-07-03 — Planning: PRD
- Produced `docs/context.md` (background/constraints/non-goals), `docs/ADRs.md` (10 architecture decision records), and `docs/PRD.md`.
- PRD structured in the three layers (ML engine / contract / agent behavior) with functional requirements, 12 user stories + acceptance criteria (tagged by test layer), and a 13-slice v1 build plan with requirement→slice traceability.
- Next: `/to-issue` (one issue per slice) → build S1 (config + init).

## 2026-07-07 — S1: config + init (#1)
- `churnpilot/config.py`: Pydantic `churn.yaml` schema (`ChurnConfig` / `SourceConfig` / `ColumnMap`, `extra="forbid"`), `load_config` raising a readable `ConfigError`, and the `CONFIG_TEMPLATE`.
- `churnpilot/cli.py`: `init` command scaffolds `churn.yaml` (won't overwrite without `--force`).
- Added deps `pydantic`, `types-PyYAML`; added `[tool.mypy]` (python 3.11 + pydantic plugin).
- `tests/test_config.py`: 12 tests (valid/default/error paths + `init` round-trip). Full suite 14 green; ruff + mypy clean. (Closes #1)

## 2026-07-07 — S2: generate (#2)
- `churnpilot/generate.py`: deterministic `make_panel()` — simulates subscriber lifetimes into a 25-column streaming churn panel with the 4 levers (watch-hours drift across cohorts, ~10% churn via bisection-solved intercept, missingness, planted `cancel_flow_visits_30d` leakage) + derived `cltv`. Vectorized grid + first-churn truncation.
- `churnpilot/cli.py`: `generate` command (writes parquet + prints summary).
- `tests/test_generate.py`: 9 tests (determinism, schema, imbalance, drift trend, missingness, leakage-trap separation, churn-is-last-row truncation, sanity). Full suite 23 green; ruff + mypy clean.
- Added mypy override for untyped `pandas`. Spec recorded in `docs/synthetic-data.md`. Full run: 8k×24 → 59,683 rows, churn 0.100, ~0.8 MB. (Closes #2)

## 2026-07-07 — S3: source + validate (#3)
- `churnpilot/source.py`: `load_data(config)` behind one interface — synthetic (`make_panel`), file (parquet/csv), sqlite (stdlib), postgres (guarded SQLAlchemy path); errors surface as `SourceError`.
- `churnpilot/validate.py`: `validate(df, config)` → graded `ValidationReport` (✔ pass / ⚠ warn / ✗ fail) covering rows, target (2 classes + positive_value present), panel-vs-snapshot mode, id uniqueness, value_col, features, missingness. Fails gracefully (no traceback).
- `churnpilot/cli.py`: `validate` command (config → data → report; non-zero exit on hard fail).
- `tests/test_source.py` (7) + `tests/test_validate.py` (10). Full suite 40 green; ruff + mypy clean. Extended mypy override to `sqlalchemy`. (Closes #3)

## 2026-07-07 — S4: profile (EDA) (#4)
- `churnpilot/profile.py`: `profile_frame(df, config)` → per-column role (config-driven for id/date/target), null rate, cardinality, numeric summary stats, and numeric-feature `target_corr`; `high_corr_features()` surfaces a leakage hint.
- `churnpilot/cli.py`: `profile` command (prints the EDA table + a `⚠ possible leakage` line); factored a shared `_load()` config+data helper (reused by `validate`).
- `tests/test_profile.py` (8): roles, numeric stats, null rates, target-corr signs, and that the leakage hint flags `cancel_flow_visits_30d` (not genuine drivers). Full suite 47 green; ruff + mypy clean. Smoke: leak at +0.92 vs. real drivers ~0.12. (Closes #4)

## 2026-07-07 — S5: metric core + metrics (#5)
- `churnpilot/metrics.py` (numpy/pandas only — the tested compute core): `ks_table` (decile KS), `psi` (frozen reference edges), `rank_order_breaks`, `gain_table`/`top_decile_lift`, `roc_auc` (rank formula), `average_precision` (PR-AUC), `precision_recall_f1`, `log_loss`, `calibration_table`/`expected_calibration_error` — all reimplemented clean-room by hand.
- `churnpilot/cli.py`: `metrics` command (KS/ROB/lift/AUC for a `--score-col` vs the target; optional `--reference` for score PSI).
- `tests/test_metrics.py` (15): PSI-identical=0, PSI-shift major, KS separable/random, ROB monotone/inverted, lift, AUC perfect/random, AP, precision/recall/F1, log-loss=ln2, calibration ECE. Full suite 62 green; ruff + mypy clean. Smoke: leakage feature 0.9998 AUC / 9.85× lift vs genuine driver 0.62 AUC. (Closes #5)

## 2026-07-07 — S6: split + the artifact/contract layer (#6)
- `churnpilot/artifacts.py`: `ArtifactBase` (Pydantic, `extra="forbid"`, `parent_sha256` lineage, `write_json`) + `content_hash(df)` — the medium contract tier foundation (ADR-009).
- `churnpilot/split.py`: `split_dataset()` with `time` (out-of-time, default) / `grouped` (disjoint subscribers) / `random` (row-wise) strategies; a leakage guard (row-disjoint, time-ordered, subscriber-overlap) that warns on random-split entity leakage; emits a `SplitManifest` artifact.
- `churnpilot/cli.py`: `split` command (writes train/val/test parquets + `split-manifest.json`; reports the leakage verdict).
- `tests/test_split.py` (9): time-ordering, grouped disjointness, random entity-leakage warning, ratios, snapshot+time error, manifest lineage + JSON round-trip, determinism. Full suite 71 green; ruff + mypy clean. Smoke: time ✔ (1,334 legit overlap) vs random ⚠ (4,822 leaked). (Closes #6)

## 2026-07-07 — S7: train (the model menu) (#7)
- `churnpilot/model.py`: `train_model()` over the menu (logistic L1 / pruned tree / rf / xgboost) in a leakage-safe `ColumnTransformer` pipeline fit on train only; optional SMOTE (`imblearn` ImbPipeline) + isotonic `CalibratedClassifierCV`; always-on `DummyClassifier` floor; `--tune` = the course's `LogisticRegressionCV` / ccp pruning / XGBoost `GridSearchCV`. Emits `ModelCard`; `save_model`/`load_model` (joblib). Mirrors the ML-course notebook stack.
- `churnpilot/cli.py`: `train` command (menu + `--smote`/`--calibrate`/`--tune`; writes model.pkl + model-card).
- Deps: `xgboost`, `imbalanced-learn`, `joblib` (+ macOS `libomp` via brew). Migrated logistic to sklearn 1.9's `l1_ratio` API (no deprecation warnings).
- `tests/test_model.py` (12): each model fits + beats floor, baseline=0.5, SMOTE/calibrate paths, tune paths (ccp + grid), model-card lineage + round-trip, save/load. Full suite 83 green; ruff + mypy clean. Smoke: xgboost 0.81 AUC (clean) vs 0.9999 (auto/leaky). (Closes #7)
