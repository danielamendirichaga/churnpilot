# churnpilot — Design Brief

Output of the grilling session. This is the raw material `/to-prd` formalizes into
`PRD.md` (three layers: ML engine / contract / agent behavior), ADRs, user stories, and
a slice breakdown. Every decision below was pressure-tested against established ML and
software-engineering practice.

---

## 0. The idea (one line)

> churnpilot is a config-driven copilot for churn/retention analysis: you point it at a
> customer table, and an AI agent (Claude) drives a deterministic, unit-tested Python
> pipeline to predict who will churn, decide who to save under a budget, and watch for
> drift — proposing and explaining every step while the data scientist stays in charge.

**Goals:** (1) a job-hunting portfolio piece for **Data Scientist / Research Scientist /
Applied Scientist** roles; (2) deeply learn the *agent + tested-CLI + typed-artifacts* pattern.

**Split of labor:** agent = judgment/explanation; deterministic tested Python = all compute;
typed artifacts with lineage = the contract. Single-agent, human-in-the-loop.

---

## 1. Decisions log (quick scan)

| # | Decision | Choice |
|---|---|---|
| 1 | Domain / world | Streaming **monthly subscription** (Netflix-style); churn = cancellation |
| 2 | Target | `churn_next_30d` — of subs active at a monthly snapshot, who cancels within 30 days (next cycle); binary |
| 3 | Unit of observation | **Panel** — one row per active subscriber per month (`observation_month` cohorts) |
| 4 | Data-shape support | Config-driven: date col present → panel (time-split + drift); absent → snapshot (stratified split; drift/time-split skip gracefully) |
| 5 | Real datasets | Synthetic = "Netflix-style" (full pipeline); Telco = real snapshot smoke test (Bank Churn alt); KKBox = real panel option |
| 6 | Model menu (capped) | logistic (L1), pruned decision tree, random forest, XGBoost |
| 7 | Model choice | **EDA-driven agent recommendation** over the menu + always-on baseline floor + `compare` step |
| 8 | Imbalance | SMOTE option (train-folds only) **+** cost-based threshold (standard method) |
| 9 | Calibration | isotonic (`CalibratedClassifierCV`) + calibration check in `evaluate` (fills a calibration gap) |
| 10 | Metrics | Union: precision/recall/F1 + log-loss **and** KS/PSI/rank-order/lift + calibration. Headline = **top-decile lift + PR-AUC** |
| 11 | Split | modes `time` (default) / `grouped` / `random`; row-level leakage guard |
| 12 | Policy | `benefit(x)=save_rate·P(churn)·CLTV − offer_cost`; budget = N offers or $; **fixed save_rate in v1** |
| 13 | Uplift | **v2** (causal / Qini) — needs a simulated A/B-test in the generator; not in v1 |
| 14 | Contract layer | **Medium** — 5 Pydantic artifacts + `parent_sha256` lineage; skip JSON-Schema-CI/versioning/walker |
| 15 | Agent autonomy | **Plan-once, run-with-checkpoints**; stop only at judgment moments |
| 16 | Seasonality | **v2**, opt-in `--seasonality` flag |
| 17 | Interface | Terminal CLI, print-to-screen, config-driven, installable, Claude-drivable; charts.py → HTML report + Streamlit dashboard |

---

## 2. Domain & data model

- **World:** streaming monthly subscription (contractual). Churn is an explicit cancellation event → clean binary label.
- **Target:** `churn_next_30d`. At each monthly snapshot, of currently-active subscribers, 1 = cancels before the next renewal (next 30 days). ~8–12% base rate (imbalanced).
- **Unit:** panel — a subscriber active Jan/Feb/Mar yields 3 rows, features *as of that month*. `observation_month` = the cohort key powering time-aware split + drift.
- **Dual-shape (config-driven):** if a `date_col` is declared → panel path (time-aware split, drift monitoring). If not → single-snapshot path (stratified-random split; `monitor` and time-split **skip gracefully** with a clear message, e.g. "no date column → drift unavailable"). Mirrors credit-lab's "time-aware **plus** random/stratified" and the "validate & fail gracefully" principle.
- **Real-dataset stance:** synthetic generator is branded "Netflix-style streaming" (invented data, relatable narrative). Real single-snapshot smoke test = **Telco Customer Churn** (or Bank Customer Churn). Real streaming panel option (if ever wanted) = **KKBox**. No real Netflix churn dataset exists.

---

## 3. Synthetic generator spec (`generate`)

One row = one active subscriber-month. Deterministic (seeded). Markers: 🎯 driver · 📉 drift · ⚠️ leakage trap · ␀ missing.

**IDs & time:** `subscriber_id` · `observation_month` · `tenure_months` 🎯
**Account/plan:** `plan_tier` (Basic/Standard/Premium) 🎯 · `monthly_price` · `payment_method` · `on_promo` · `promo_months_left` 🎯 · `household_profiles`
**Engagement:** `watch_hours_30d` 🎯📉␀ · `active_days_30d` 🎯 · `days_since_last_watch` 🎯 (strongest) · `watch_hours_trend` 🎯 · `titles_started_30d` · `titles_completed_30d` · `avg_session_minutes` ␀
**Friction:** `support_tickets_30d` 🎯 · `payment_failures_30d` 🎯
**Demographics:** `age` ␀ · `region` · `signup_device`
**Value:** `cltv` (carried or derived = `monthly_price × expected_remaining_tenure`) — needed by the policy layer
**Target:** `churn_next_30d`
**⚠️ Planted leakage trap:** `cancel_flow_visits_30d` — near-perfectly predicts churn; included so the agent has something concrete to catch/flag.

**The four levers:**
- **Drift:** `watch_hours_30d` erodes *down* across cohorts (engagement erosion) → non-trivial PSI, makes time-aware split matter.
- **Imbalance:** ~8–12% monthly churn → forces lift/PR metrics.
- **Missingness:** engagement fields missing for brand-new subs; `age` ~8%.
- **Leakage trap:** `cancel_flow_visits_30d` (above).

**Deferred (v2):** `--seasonality` opt-in (January post-holiday spike; needs ≥24 months to be learnable). Post-finale cliff = a future *root-cause* demo, not a seasonality lever. **Uplift A/B-test hook** (treatment assignment + heterogeneous response) added in v2, not v1.

---

## 4. Split & leakage (`split`)

- **Modes:** `time` (default, out-of-time: train = months ≤ T, test > T) · `grouped` (all of a subscriber's rows in one split — answers the cold-start / new-subscriber question) · `random` (row-wise — **the tempting-wrong one**).
- **Entity-leakage trap (panel-specific):** `random` scatters the same `subscriber_id` across train & test → the model memorizes individuals (entity leakage) + sees their future (temporal leakage) → gorgeous metrics, production collapse. The **`random`-vs-`time` metric gap is the teaching demo.**
- **Correct nuance:** under `time`, subscribers *do* overlap across the boundary (early months in train, later in test) — that's **correct** (mirrors deployment). What must never overlap is a subscriber-**month** row or future info.
- **Leakage guard:** assert row-level disjointness on `(subscriber_id, observation_month)`, assert temporal ordering; report subscriber overlap (informational for `time`, error for `random`).
- **Teaching point:** credit-lab's "assert disjoint on `application_id`" guard **doesn't transfer** — applications were unique, subscribers recur.

---

## 5. Modeling (`train`, `compare`)

- **Menu (capped):** `logistic` (L1 via `LogisticRegressionCV`, C tuned by CV → embedded feature selection) · `decision-tree` (pruned via `ccp_alpha`, interpretability/visualization) · `random-forest` (bagging, robust low-tuning) · `xgboost` (boosting, likely top performer, `GridSearchCV` + `StratifiedKFold` + early stopping).
- **Baseline floor:** always run (majority-class / simple logistic) — everything must beat it. Not a "choice," a reference.
- **Model choice = EDA-driven agent recommendation** over the menu (agent reads `profile` output, recommends a family *with reasons*, DS decides), then `compare` fits the shortlist and **ranks on held-out + stability** ("select on stability, not just peak AUC": small train→test drop, low score-PSI).
- **Standard, defensible methods:**
  - Leakage-safe preprocessing by construction — `ColumnTransformer` + `Pipeline`, imputers/encoders/scalers **fit on train folds only**.
  - **SMOTE** option via `imblearn` ImbPipeline (oversample train folds only). Standard caveat honored: SMOTE mainly ↑recall at ↓precision; often rivaled by cost-based thresholds — so we support both and let the agent compare.
  - **Calibration** (isotonic) — added because the cost-based threshold assumes calibrated probabilities.
- **Convention:** higher score = higher churn risk (documented — "half of scorecard bugs are a flipped sign").

---

## 6. Metrics (`evaluate`)

Union of the two conventions:
- **Standard classification:** precision / recall / F1, log-loss, confusion matrix, cost-based threshold.
- **Credit-lab:** KS (decile-table), PSI, rank-order-breaks, lift/gain, calibration; score-PSI train→test; metric drops.
- **Headline for churn targeting:** **top-decile lift + PR-AUC** (AUC is table stakes).
- Per-segment slices (e.g. by `plan_tier`, `region`).

---

## 7. Policy (`simulate-policy`) — the crown jewel

- Grounded in a standard cost-based expected-loss method, extended from "pick a threshold" to "pick whom to save under a budget."
- **Formula:** `benefit(x) = save_rate · P(churn|x) · CLTV(x) − offer_cost`. Rank subscribers by `benefit`, target top ones until **budget** exhausted (budget = **N offers** or **$ spend**).
- **Output:** targeted set, expected retained value, expected spend, trade-off curve (retained value vs. budget), by segment.
- **v1 assumption:** `save_rate` is a **single configurable constant**, stated honestly in the report.
- **v2 upgrade (uplift):** replace flat `save_rate` with per-customer uplift `τ(x)=P(stay|offer)−P(stay|no offer)` → target *persuadables*, not lost-causes/sure-things. Needs a **simulated A/B test** in the generator (treatment + heterogeneous response: persuadables / sure-things / lost-causes / sleeping-dogs) and **Qini / uplift-at-k** evaluation. (Uplift needs treatment variation; randomized A/B is the gold standard; observational needs confounding correction.)

---

## 8. Contract / artifact layer — **Medium**

5 Pydantic-typed artifacts, each with a `parent_sha256` lineage field, params, and key stats; **print-to-screen + JSON sidecar**:

| Command | Artifact | Carries |
|---|---|---|
| `split` | `split-manifest` | strategy, windows, row counts, leakage-guard result |
| `train` | `model-card` | model family, chosen hyperparams, train metrics, feature list |
| `evaluate` | `eval-report` | full metric pack, calibration, per-segment slices |
| `simulate-policy` | `policy-report` | cost params, save_rate, budget, targeted set, retained value |
| `monitor` | `drift-report` | per-feature PSI, threshold, retrain flag |

**Skipped (heavy, parked as an optional future "hardening" phase only if MLOps roles are added):** committed JSON-Schema exports + CI-sync test, per-artifact versioning, `validate-artifact` lineage-walker. Rationale: single-agent + one consumer + portfolio timeframe; target roles (DS/Research/Applied Scientist) reward reproducibility (which medium gives) but not platform governance.

---

## 9. Agent behavior (PRD part 3)

- **Autonomy: plan-once, run-with-checkpoints.** Agent proposes a short plan → DS approves once → agent runs the pipeline, narrating → stops only at genuine judgment moments (model choice, policy params, leakage/drift red flags).
- **Guardrails (behavioral acceptance criteria):**
  - **Never** computes a metric in-prompt — always calls the CLI.
  - **Never** includes a suspected leakage feature silently — flags `cancel_flow_visits_30d` and asks.
  - **Always** warns if `--split random` is chosen on panel data.
  - **Never** claims a result it didn't actually run (working-result principle).
  - **Proposes + waits** on: model choice (from EDA), policy params (`save_rate`/`offer_cost`/`budget`), acting on a drift alert.
  - **Decides freely** (low-stakes): which profiling to run, narration, formatting.
  - **Never** treats synthetic numbers as real, or changes the target definition on its own.

---

## 10. Scope tiers

- **v1 (Minimum Lovable — complete core loop):** `generate` → `config`/`validate` → `profile` → `split` → `train` → `compare` → `evaluate` → `simulate-policy` → `report` → `monitor`. Medium artifacts + lineage throughout. Agent can drive the whole flow.
- **v1.1 (fast-follow):** `dashboard` (Streamlit — interactive policy sliders; reuses `charts.py`).
- **v2 (depth modules — the differentiators):** **uplift/causal** (A/B-test generator hook + Qini eval + uplift-based policy) · `--seasonality` opt-in + seasonal-aware monitor · *(optional)* heavy contract hardening.

---

## 11. Config (`churn.yaml`) & interface

- **Config declares** (nothing hardcoded): `source` (kind: postgres/sqlite/file/synthetic, dsn/path, table); `schema` mapping (`id_col`, `date_col` [optional → toggles panel vs snapshot], `target_col`, `positive_value`, `value_col`/CLTV, `features` list or `"auto"`).
- **Interface:** terminal CLI (`churnpilot <command>`), print-to-screen, installable (`pip install`), Claude-drivable via `AGENTS.md`.
- **Charts:** single tested `charts.py` (matplotlib/plotly) is the source of truth; both the HTML `report` and the Streamlit `dashboard` call the same chart functions.

---

## 12. Tech stack & conventions

- **Python 3.11**, `uv`, `typer` CLI. Deterministic: **seed everything**.
- **Deps:** pandas, numpy, pyarrow, pyyaml (core); scikit-learn, **xgboost**, **imbalanced-learn** (SMOTE), **pydantic** (artifacts), matplotlib/plotly, streamlit (model/viz layers). Dev: pytest, ruff, mypy.
  - *(All deps now declared in `pyproject.toml`; `xgboost`/`imbalanced-learn` landed in S7.)*
- **The tested core (metrics/validate) imports only numpy/pandas** — never sklearn/xgboost (keeps that layer light & fast to test).
- **Four principles** (from credit-lab, restated for churn): DS-leads (propose don't decide) · compute in tested code not the prompt · working-result enforcement (nothing done until it runs green) · multi-entry (any stage accepts a user file/artifact).

---

## 13. Open items for `/to-prd` to formalize

- Turn §2–§11 into **user stories** (acceptance criteria) and a **slice breakdown** (one requirement ↔ one slice), following the v1 build order.
- Draft **ADRs** for the load-bearing calls: single-agent (no orchestration); time-aware split default; agent-never-computes; medium contract tier; uplift deferred to v2; fixed save_rate in v1.
- Structure PRD in the three layers: **ML engine** (unit/integration tests) · **contract/interface** (schemas + CLI signatures) · **agent behavior** (behavioral/E2E tests).
