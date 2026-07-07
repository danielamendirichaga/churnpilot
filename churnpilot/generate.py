"""Deterministic synthetic "Netflix-style streaming" churn panel generator.

Pure synthetic numpy/pandas — **no real data, no PII**. Given a seed, :func:`make_panel`
produces exactly the same frame every time.

One row = one active subscriber in one month (``observation_month``). Subscribers are
simulated over their lifetime: they sign up, their engagement evolves monthly, and each
month a latent-logit hazard decides whether they churn in the next 30 days
(``churn_next_30d``). A churned subscriber's last row carries the label 1 and they leave.

The frame is intentionally imperfect (see ``docs/synthetic-data.md``):

* **Drift** — ``watch_hours_30d`` mean declines across ``observation_month`` cohorts.
* **Imbalance** — ~8–12% monthly churn (intercept tuned by bisection).
* **Missingness** — engagement blank for first-month subs; ``age`` ~8% missing.
* **Leakage trap** — ``cancel_flow_visits_30d`` spikes with churn (planted, with noise).

Usage::

    python -m churnpilot.generate  # or: churnpilot generate --out data/churn_panel.parquet
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TARGET = "churn_next_30d"
DRIFT_FEATURE = "watch_hours_30d"
COHORT_START = "2023-01"
TARGET_CHURN_RATE = 0.10

PLANS = np.array(["Basic", "Standard", "Premium"])
PLAN_PROBS = [0.50, 0.35, 0.15]
PLAN_PRICE = {"Basic": 7, "Standard": 12, "Premium": 18}
REGIONS = np.array(["north", "south", "east", "west"])
REGION_PROBS = [0.30, 0.30, 0.20, 0.20]
DEVICES = np.array(["ios", "android", "web", "tv"])
DEVICE_PROBS = [0.35, 0.35, 0.15, 0.15]
PAYMENT_METHODS = np.array(["card", "paypal", "wallet"])
PAYMENT_PROBS = [0.70, 0.20, 0.10]


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _keep_mask(churn_row: np.ndarray, counts: np.ndarray) -> np.ndarray:
    """Per subscriber (contiguous blocks of length ``counts``), keep rows up to and
    including the first churn event; drop everything after (they have left)."""
    block_start = np.cumsum(counts) - counts
    cum_incl = np.cumsum(churn_row)
    cum_before_block = np.where(block_start > 0, cum_incl[block_start - 1], 0)
    within_incl = cum_incl - np.repeat(cum_before_block, counts)
    within_before = within_incl - churn_row
    return within_before == 0


def make_panel(n_subscribers: int = 8000, n_months: int = 24, seed: int = 42) -> pd.DataFrame:
    """Build the synthetic streaming churn panel. Same ``(n_subscribers, n_months, seed)``
    → identical frame."""
    rng = np.random.default_rng(seed)
    n = n_subscribers

    # --- static per-subscriber traits ---------------------------------------
    # Signup month index; negative = signed up before the observation window.
    signup_idx = rng.integers(-11, n_months, size=n)
    plan = rng.choice(PLANS, size=n, p=PLAN_PROBS)
    monthly_price = np.array([PLAN_PRICE[p] for p in plan], dtype=np.int64)
    region = rng.choice(REGIONS, size=n, p=REGION_PROBS)
    device = rng.choice(DEVICES, size=n, p=DEVICE_PROBS)
    payment = rng.choice(PAYMENT_METHODS, size=n, p=PAYMENT_PROBS)
    household = rng.integers(1, 6, size=n)
    age_true = np.clip(rng.normal(38.0, 12.0, n), 18, 80).round()
    engagement = np.clip(rng.lognormal(2.6, 0.5, n), 0.5, 80.0)  # base watch hours/mo
    promo_len = rng.choice([0, 0, 0, 3, 6], size=n)  # months of intro promo (0 = none)
    age_missing = rng.random(n) < 0.08

    # --- build the full subscriber-month grid (before churn truncation) ------
    start = np.maximum(signup_idx, 0)
    counts = n_months - start
    total = int(counts.sum())
    sub = np.repeat(np.arange(n), counts)
    block_start_global = np.cumsum(counts) - counts
    offsets = np.arange(total) - np.repeat(block_start_global, counts)
    month_idx = np.repeat(start, counts) + offsets
    tenure = month_idx - np.repeat(signup_idx, counts) + 1  # months since signup (>=1)

    # --- dynamic per-row engagement features (as-of that month) --------------
    watch_mean = engagement[sub] * (1.0 - 0.02 * month_idx)  # DRIFT: declines by cohort
    watch = np.clip(rng.normal(watch_mean, np.maximum(watch_mean * 0.30, 0.5)), 0.0, 200.0)
    days_since = np.clip(
        np.round(30.0 / (1.0 + watch / 2.5) + rng.normal(0, 2, total)), 0, 30
    ).astype(np.int64)
    active_days = np.clip(
        np.round(30.0 * (1.0 - np.exp(-watch / 10.0)) + rng.normal(0, 2, total)), 0, 30
    ).astype(np.int64)
    titles_started = rng.poisson(np.clip(watch / 2.0, 0, 50)).astype(np.int64)
    titles_completed = rng.binomial(titles_started, 0.6)
    avg_session = np.clip(
        watch * 60.0 / np.maximum(active_days, 1) + rng.normal(0, 10, total), 1.0, 400.0
    )
    support_tickets = rng.poisson(0.20, total).astype(np.int64)
    payment_failures = rng.poisson(0.03, total).astype(np.int64)

    # watch_hours_trend = change vs. previous month (0 in the first observed month)
    prev = np.empty(total)
    prev[1:] = watch[:-1]
    prev[block_start_global] = np.nan
    trend = np.where(np.isnan(prev), 0.0, watch - prev)

    promo_left = np.clip(np.repeat(promo_len, counts) - (tenure - 1), 0, None)
    promo_expiring = (np.repeat(promo_len, counts) > 0) & (promo_left <= 1)

    # --- latent churn hazard (on true, pre-missing values) -------------------
    base_logit = (
        -0.045 * (watch - 15.0)
        + 0.05 * days_since
        - 0.035 * tenure
        - 0.06 * trend
        + 0.70 * promo_expiring.astype(float)
        + 0.30 * support_tickets
        + 0.90 * payment_failures
        - 0.25 * (np.repeat(plan == "Premium", counts)).astype(float)
    )
    churn_u = rng.random(total)

    # Solve the intercept (bisection) so the kept-row churn rate ~= target.
    def realized_rate(intercept: float) -> float:
        churn_row = churn_u < _sigmoid(intercept + base_logit)
        keep = _keep_mask(churn_row, counts)
        kept = int(keep.sum())
        return float((keep & churn_row).sum() / kept) if kept else 0.0

    lo, hi = -15.0, 15.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if realized_rate(mid) > TARGET_CHURN_RATE:
            hi = mid
        else:
            lo = mid
    intercept = 0.5 * (lo + hi)

    churn_row = (churn_u < _sigmoid(intercept + base_logit)).astype(np.int64)
    keep = _keep_mask(churn_row.astype(bool), counts)

    # --- assemble kept rows --------------------------------------------------
    base = pd.Period(COHORT_START, freq="M")
    min_idx = int(signup_idx.min())
    ext = pd.period_range(base + min_idx, periods=n_months - min_idx, freq="M")
    observation_month = ext[(month_idx - min_idx)].to_timestamp()
    signup_month = ext[(np.repeat(signup_idx, counts) - min_idx)].to_timestamp()

    age = np.where(age_missing[sub], np.nan, age_true[sub])

    # Missingness on engagement for brand-new subscribers (tenure == 1).
    new_missing = (tenure == 1) & (rng.random(total) < 0.5)
    watch_col = np.where(new_missing, np.nan, watch)
    avg_session_col = np.where(new_missing, np.nan, avg_session)

    # Leakage trap: visits to the cancel page spike for churners (with noise).
    cancel_visits = np.where(
        churn_row == 1, rng.poisson(4.0, total) + 1, rng.poisson(0.03, total)
    ).astype(np.int64)

    expected_life = np.clip(np.round(6.0 + 0.7 * engagement), 3, 48)[sub]
    cltv = (monthly_price[sub] * expected_life).astype(np.int64)

    df = pd.DataFrame(
        {
            "subscriber_id": (sub + 1).astype(np.int64),
            "observation_month": observation_month,
            "signup_month": signup_month,
            "tenure_months": tenure.astype(np.int64),
            "plan_tier": plan[sub],
            "monthly_price": monthly_price[sub],
            "payment_method": payment[sub],
            "on_promo": promo_left > 0,
            "promo_months_left": promo_left.astype(np.int64),
            "household_profiles": household[sub].astype(np.int64),
            "watch_hours_30d": watch_col.round(2),
            "active_days_30d": active_days,
            "days_since_last_watch": days_since,
            "watch_hours_trend": trend.round(2),
            "titles_started_30d": titles_started,
            "titles_completed_30d": titles_completed,
            "avg_session_minutes": avg_session_col.round(1),
            "support_tickets_30d": support_tickets,
            "payment_failures_30d": payment_failures,
            "age": age,
            "region": region[sub],
            "signup_device": device[sub],
            "cancel_flow_visits_30d": cancel_visits,
            "cltv": cltv,
            TARGET: churn_row,
        }
    ).loc[keep]

    return df.sort_values(["subscriber_id", "observation_month"]).reset_index(drop=True)


def summarize(df: pd.DataFrame) -> str:
    """Human-readable summary (for the CLI, printed to stderr)."""
    first = df["observation_month"].min()
    last = df["observation_month"].max()
    null_rates = {c: round(float(df[c].isna().mean()), 4) for c in df.columns if df[c].isna().any()}
    return "\n".join(
        [
            f"rows            : {len(df):,}",
            f"subscribers     : {df['subscriber_id'].nunique():,}",
            f"cohorts         : {df['observation_month'].nunique()} months "
            f"({first:%Y-%m} → {last:%Y-%m})",
            f"churn rate      : {df[TARGET].mean():.4f} ({TARGET})",
            f"null rates      : {null_rates if null_rates else '{}'}",
            f"drift feature   : {DRIFT_FEATURE} (mean declines across cohorts)",
        ]
    )
