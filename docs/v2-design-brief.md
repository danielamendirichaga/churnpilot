# churnpilot v2 — uplift / causal — design brief

> **Status: ACCEPTED (2026-07-07).** Owner accepted all recommendations. Resolutions: (1) full
> 4-quadrant treatment; (2) hand-rolled S- + T-learner, **X-learner deferred to v2.1**; (3) base
> learner **defaults to logistic** (interpretable τ, most stable in v1's `compare`) but configurable;
> (4) nothing added — scope stays tight. This is the v2 PRD; slices S14–S18 become issues.

## The shift in one line

v1 ranks customers by **risk** — `P(churn | x)`. v2 ranks by **uplift** — `τ(x)`, the *causal effect
of the offer on retention*. They select different people:

| segment | risk | uplift τ | action |
|---|---|---|---|
| **persuadable** | high | large + | **target** 🎯 |
| **sure thing** | low | ≈0 | skip 💸 |
| **lost cause** | high | ≈0 | skip 💸 (a risk model wastes budget here) |
| **sleeping dog** | any | **negative** | **avoid** ⚠️ (the offer reminds them to cancel) |

A risk model spends the whole budget on lost causes (highest risk!). An uplift model finds the
persuadables and avoids the sleeping dogs. Quantifying that gap is the v2 thesis.

**Why it needs an experiment:** you cannot observe "did the offer change their mind?" — only the
factual outcome under the arm they got. So v2 starts by simulating a randomized A/B test.

---

## Decisions (recommended — react to each)

### 1. Treatment simulation — **FULL 4-quadrant** ✅ (rec)
Add to the generator a randomized `treated ∈ {0,1}` (~50/50, independent of features → clean
experiment). Give each customer a latent uplift `τ(x)` that **varies** and is **partly orthogonal to
risk**, spanning all four quadrants incl. **sleeping dogs (τ<0)**. Churn under treatment:
`P(churn | treated=1, x) = clip(P(churn | 0, x) − τ(x), 0, 1)` (τ>0 lowers churn = good; τ<0 raises it).
The generator knows **both** potential outcomes `Y(0), Y(1)` → we can compute **true** τ for honest
Qini/validation, but the emitted dataset shows only the factual outcome. Persuadability is driven by a
distinct signal (e.g. engaged-but-slipping mid-tenure users) so the uplift model learns something the
risk model can't; sleeping dogs skew toward high-friction/high-support-ticket users.
*Alternatives: positive-only (no backfire lesson); uniform (thesis collapses — rejected).*

### 2. Uplift learners — **hand-implemented meta-learners over `model.py`** ✅ (rec)
- **S-learner** — one model with `treated` as a feature; `τ̂(x)=f(x,1)−f(x,0)` (retention framing: `−Δchurn`).
- **T-learner** — two models (treated / control); `τ̂(x)=f₀(x)−f₁(x)` on churn prob.
- **X-learner** — *optional* (imputed effects + propensity); stronger but more code → v2 if it fits, else v2.1.

Rationale: meta-learners **reuse the existing tested model stack** (logistic/tree/rf/xgboost) — no heavy
new dep (no `causalml`), and hand-rolling them shows genuine causal understanding (better portfolio
signal than importing a black box). New artifact: `UpliftCard`.

### 3. Uplift evaluation — **Qini + uplift deciles + true-vs-estimated** ✅ (rec)
- **Qini curve + Qini coefficient** — the standard uplift metric (AUC's analogue for targeting).
- **Uplift-by-decile** — is estimated τ monotone, and does the top decile carry the effect?
- **True-vs-estimated τ check** — only possible because the synthetic generator knows the counterfactual;
  a rigor flourish (validate the estimator against ground truth). New artifact: `QiniReport`; `uplift-eval` CLI.

### 4. Policy — **add `--rank-by uplift|risk` + contrast** ✅ (rec)
`benefit_uplift(x) = τ(x)·CLTV − offer_cost` (spend where the *incremental* retention value beats the
cost). Keep v1's risk policy intact; the headline is the **contrast**: *at the same budget, targeting by
uplift retains $X more than targeting by risk and avoids N sleeping dogs.* That contrast is v2's money chart.

### 5. Scope boundary — **uplift only for v2** ✅ (rec)
Seasonality (a time-series concern) and real-world A/B data → later (v2.1+). Synthetic-only is a *feature*
here: known counterfactuals make honest Qini teaching possible. Keep v2 focused on the causal story.

---

## Proposed slices (S14–S18)

- **S14 — generator treatment simulation.** `treated` + heterogeneous `τ(x)` + both potential outcomes;
  treatment config; validate the 4 quadrants exist and uplift ≠ risk. Tests: randomization balance,
  τ heterogeneity, sleeping dogs present, factual/counterfactual consistency.
- **S15 — uplift models.** `uplift.py`: S- + T-learner over `model.py`; `UpliftCard`; `train-uplift` CLI.
  Tests: recovers +τ for persuadables, −τ for sleeping dogs, T/S sanity.
- **S16 — Qini / uplift eval.** `qini.py`: Qini curve + coefficient + uplift deciles + true-vs-estimated;
  `QiniReport`; `uplift-eval` CLI. Tests: Qini(model) > random, deciles monotone, ground-truth recovery.
- **S17 — uplift policy + contrast.** `policy.py` gains `--rank-by uplift|risk` + `benefit_uplift`; a
  risk-vs-uplift contrast (extra retained value, sleeping dogs avoided). Tests: uplift ≥ risk on synthetic truth.
- **S18 — v2 report + docs.** Qini + uplift-vs-risk charts in `charts.py`/report; README/docs; v2 capstone E2E.

## Resolved (owner-accepted 2026-07-07)
1. **Treatment richness** — full 4-quadrant, incl. sleeping dogs (τ<0). ✅
2. **X-learner** — deferred to v2.1; v2 ships S- + T-learner. ✅
3. **Base learner default** — logistic (interpretable τ; won v1's stability contest); configurable via `--model`. ✅
4. **Additions** — none; scope stays tight (seasonality / real A/B data / X-learner = later). ✅
