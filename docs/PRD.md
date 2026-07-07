# churnpilot — PRD

Product requirements, structured in the three layers from `WORKFLOW.md` §2.2. Every
requirement is anchored to a **slice** (§7), which becomes a GitHub issue via `/to-issue`.
Background: `context.md` · Decisions: `ADRs.md` · Full design: `DESIGN_BRIEF.md`.

## 1. Overview

churnpilot: a config-driven, single-agent copilot for churn/retention analysis. The AI does
judgment/explanation; a deterministic, unit-tested CLI does all compute; typed artifacts with
lineage are the contract. See `context.md` for goals, users, constraints, and non-goals.

## 2. Scope

- **v1** (this PRD's focus): `generate → validate → profile → split → train → compare →
  evaluate → simulate-policy → report → monitor`, all with medium artifacts + lineage.
- **v1.1:** `dashboard` (Streamlit).
- **v2:** uplift/causal (+ A/B-test generator hook, Qini, uplift-policy) · `--seasonality` ·
  optional heavy contract hardening.

---

## 3. Layer 1 — Deterministic ML engine
*Acceptance = unit/integration tests. The tested metric/validate core imports only numpy/pandas.*

| ID | Requirement |
|---|---|
| **FR-GEN** | `generate` produces a deterministic (seeded) synthetic streaming **panel** (subscriber-month rows) with the feature schema in DESIGN_BRIEF §3, the 4 levers (drift on `watch_hours_30d`, ~8–12% imbalance, missingness, planted `cancel_flow_visits_30d` leakage trap), and a `cltv` value field. |
| **FR-SRC** | One loader serves `db` / `file` / `synthetic` behind a single interface, selected by config. |
| **FR-VAL** | `validate` checks data against the config and **fails gracefully** — reports missing/renamed columns, target class balance, id uniqueness, null rates, and (if no `date_col`) that drift/time-split will be skipped. No stack traces; clear exit. |
| **FR-PROF** | `profile` reports per-column role, null rate, cardinality, numeric summaries, and target relationship (the EDA numbers the agent reasons over). |
| **FR-MET** | A pure, tested metric core: decile-KS, PSI (frozen reference edges), rank-order-breaks, lift/gain + top-decile lift, precision/recall/F1, log-loss, calibration. Deterministic; documented score direction (higher = higher churn risk). |
| **FR-SPL** | `split` supports `time` (default, out-of-time) / `grouped` / `random`, with a leakage guard (row-level disjoint on `(subscriber_id, observation_month)` + temporal ordering; subscriber-overlap report). |
| **FR-TRN** | `train` fits a model from the capped menu (logistic L1 · pruned tree · random forest · xgboost) in a **leakage-safe** `Pipeline`/`ColumnTransformer` (fit on train only), with optional SMOTE (train-folds only) and isotonic calibration; always also fits the **baseline floor**. |
| **FR-CMP** | `compare` fits the shortlist and ranks candidates on held-out performance **and stability** (train→test metric drop, score-PSI). |
| **FR-EVAL** | `evaluate` loads a model, scores held-out data, and reports the **union metric pack** + calibration check + per-segment slices (e.g. by `plan_tier`). |
| **FR-POL** | `simulate-policy` computes `benefit(x)=save_rate·P(churn)·CLTV − offer_cost`, targets under a **budget (N offers or $ spend)**, and reports the targeted set, expected retained value, spend, and a trade-off curve by segment. |
| **FR-RPT** | `report` renders a shareable **HTML report** (gain/lift, PSI-over-time, policy trade-off, calibration) from a single tested `charts.py`. |
| **FR-MON** | `monitor` computes per-feature PSI across cohorts vs. a reference and raises a **retrain flag** when drift crosses a threshold (skips gracefully with no `date_col`). |

## 4. Layer 2 — Contract / interface
*Acceptance = schema/format checks.*

| ID | Requirement |
|---|---|
| **FR-CFG** | `churn.yaml` declares `source` (kind/dsn/path/table) + `schema` mapping (`id_col`, `date_col?`, `target_col`, `positive_value`, `value_col`, `features` or `"auto"`). `init` scaffolds a template; loader validates it (Pydantic). |
| **FR-CLI** | `typer` CLI, one command per capability, consistent flags, `--help` for each, human-readable print-to-screen. Command set = DESIGN_BRIEF §10 (v1). |
| **FR-ART** | 5 Pydantic-typed artifacts (`split-manifest`, `model-card`, `eval-report`, `policy-report`, `drift-report`), each with `parent_sha256` **lineage**, params, and key stats; written as JSON sidecars alongside human-readable output. |
| **FR-DET** | Seeds and key params are recorded in each artifact; re-running with the same inputs reproduces identical outputs. |

## 5. Layer 3 — Agent behavior
*Acceptance = behavioral / E2E checks (see user stories US-A*).*

| ID | Requirement |
|---|---|
| **FR-AGT-PLAN** | Autonomy = **plan-once, run-with-checkpoints**: propose a short plan, get one approval, run while narrating, stop only at judgment moments (model choice, policy params, red flags). |
| **FR-AGT-GUARD** | Guardrails: never computes a metric in-prompt (calls the CLI); flags `cancel_flow_visits_30d` as leakage and asks; warns if `--split random` on panel data; never claims an un-run result; proposes+waits on model/policy decisions; never treats synthetic numbers as real or changes the target unasked. |
| **FR-AGT-DOC** | `AGENTS.md` encodes the architecture rules, command map, and guardrails so a fresh session is primed. |

---

## 6. User stories & acceptance criteria

*Layer tag on each criterion: [E]=engine unit/integration · [C]=contract/schema · [A]=agent behavioral.*

- **US-1 (data):** *As a DS, I want realistic synthetic churn data so I can build/test without real data.*
  - [E] `generate --seed S` twice → byte-identical output. [E] churn rate ∈ ~8–12%; `watch_hours_30d` mean declines across cohorts (PSI > 0.1 last vs first); documented missingness present. [C] emits a dataset the config can map.
- **US-2 (ingest/validate):** *As a DS, I want to point the tool at my data and be told what's wrong before modeling.*
  - [E] missing `target_col` → clear error, non-zero exit, no traceback. [E] no `date_col` → warns drift/time-split unavailable. [A] agent surfaces the validation report in plain words.
- **US-3 (EDA):** *As a DS, I want a profile of my data so the agent can recommend a model.*
  - [E] `profile` reports role/null/cardinality/target-corr per column. [A] agent flags `cancel_flow_visits_30d` as likely leakage and asks before using it.
- **US-4 (metrics):** *As a DS, I want trustworthy, tested churn metrics.*
  - [E] PSI(identical)=0; KS≈0 on random score, high on separable; lift/rank-order match hand-computed fixtures.
- **US-5 (split):** *As a DS, I want an honest, leakage-safe split.*
  - [E] `time` split has train windows strictly before test; guard passes. [E] `random` on panel → guard reports subscriber overlap. [A] agent recommends `time`, warns against `random`, and can show the metric gap.
- **US-6 (train):** *As a DS, I want to fit a model the agent recommended from EDA, with a floor to beat.*
  - [E] preprocessing fit on train only (no leakage); baseline floor reported; SMOTE/calibration optional and seeded. [C] `model-card` artifact with chosen family, hyperparams, lineage. [A] agent proposes a family with reasons, waits for approval.
- **US-7 (compare):** *As a DS, I want candidates ranked on stability, not just peak AUC.*
  - [E] `compare` outputs a ranked table incl. train→test drop + score-PSI. [A] agent narrates the performance-vs-stability trade-off and lets me pick.
- **US-8 (evaluate):** *As a DS, I want the full metric pack + calibration on held-out data.*
  - [E] union metrics + calibration + per-segment slices. [C] `eval-report` artifact with lineage.
- **US-9 (policy):** *As a DS, I want to know whom to save under a budget.*
  - [E] `benefit(x)` ranking; budget honored (N or $); trade-off curve by segment. [C] `policy-report` records save_rate/offer_cost/budget. [A] agent proposes params, states the fixed-save_rate assumption honestly, waits.
- **US-10 (report):** *As a DS, I want a shareable report to show stakeholders.*
  - [E] `report` writes a self-contained HTML with the key charts from `charts.py`.
- **US-11 (monitor):** *As a DS, I want to be warned when the model is going stale.*
  - [E] per-feature PSI across cohorts; retrain flag when threshold crossed; graceful skip if no dates. [C] `drift-report` artifact. [A] agent proposes (not auto-executes) a retrain on a flag.
- **US-12 (drive it):** *As a DS, I want the agent to run the whole thing while I stay in charge.*
  - [A] plan-once → approve → run-with-checkpoints; every number came from a CLI call; nothing claimed that wasn't run.

---

## 7. Slice breakdown (build plan → issues)

> **Progress: S1–S7 shipped** (config → generate → source+validate → profile → metrics → split →
> train); **S8 (`compare`) is next.** See `STATUS.md` / `CHANGELOG.md` for the live state.

Each slice is one shippable unit → one GitHub issue. **DoD (every slice):** static (ruff/mypy) →
unit → integration → behavioral/E2E green · new artifact validates (if any) · `STATUS.md` +
`CHANGELOG.md` + issue updated · `AGENTS.md` updated if conventions changed. Order follows the v1 build order.

| Slice | Name | Covers | Key deliverables |
|---|---|---|---|
| **S0** | Setup | — | ✅ done (package, venv, CI-less repo, keystone docs) |
| **S1** | Config + `init` | FR-CFG, FR-CLI | `churn.yaml` Pydantic schema, loader+validation, `init` scaffolds a template |
| **S2** | `generate` | FR-GEN, FR-DET | Seeded synthetic panel generator (schema + 4 levers + cltv); determinism test |
| **S3** | `source` + `validate` | FR-SRC, FR-VAL | Unified loader (db/file/synthetic); graceful validation report |
| **S4** | `profile` | FR-PROF | Per-column profiling + target relationship |
| **S5** | Metric core + `metrics` | FR-MET | Tested pure functions (KS/PSI/ROB/lift + P/R/F1/log-loss/calibration); `metrics` command |
| **S6** | `split` | FR-SPL, FR-ART | `time`/`grouped`/`random` + leakage guard; `split-manifest` artifact |
| **S7** | `train` | FR-TRN, FR-ART | Model menu + leakage-safe pipeline + SMOTE + calibration + baseline; `model-card` artifact |
| **S8** | `compare` | FR-CMP | Fit shortlist, rank on stability |
| **S9** | `evaluate` | FR-EVAL, FR-ART | Union metric pack + calibration + segments; `eval-report` artifact |
| **S10** | `simulate-policy` | FR-POL, FR-ART | `benefit(x)`, budget (N/$), trade-off; `policy-report` artifact |
| **S11** | `charts` + `report` | FR-RPT | Single tested `charts.py`; HTML report |
| **S12** | `monitor` | FR-MON, FR-ART | Per-feature PSI drift + retrain flag; `drift-report` artifact |
| **S13** | Agent wiring + package | FR-AGT-*, FR-CLI | Finalize `AGENTS.md` guardrails/command-map; behavioral checks; `pip install .` + README quickstart |

**v1.1:** S14 `dashboard` (Streamlit). **v2:** S15 uplift (A/B-test generator hook + uplift models + Qini + uplift-policy), S16 `--seasonality`, S17 (optional) heavy contract hardening.

### Requirement → slice traceability
FR-CFG→S1 · FR-GEN/FR-DET→S2 · FR-SRC/FR-VAL→S3 · FR-PROF→S4 · FR-MET→S5 · FR-SPL→S6 ·
FR-TRN→S7 · FR-CMP→S8 · FR-EVAL→S9 · FR-POL→S10 · FR-RPT→S11 · FR-MON→S12 ·
FR-CLI→S1/S13 · FR-ART→S6–S12 · FR-AGT-*→S13 (guardrails exercised throughout).
