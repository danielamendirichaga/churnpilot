# Synthetic dataset — churnpilot `generate`

Spec for the seeded synthetic "Netflix-style streaming" panel produced by `generate` (S2).

## Structure & generation (the DGP)
- **Unit of observation:** one row = one active subscriber in one month (panel data).
- **Method:** simulate subscriber lifetimes — assign each a signup month + fixed traits (plan, region, signup device, age, monthly price), then evolve monthly engagement (watch hours, active days, days-since-last-watch, tickets).
- **Churn mechanism:** each active month, a latent logit of the drivers → churn probability → Bernoulli draw for `churn_next_30d`; a churned subscriber exits after that month (their last row carries label = 1).
- **Signal:** churn is driven by low engagement, short tenure, expiring promo, support tickets (↑ risk) and heavy watching / long tenure (↓ risk) — real, learnable structure.

## Deliberate levers (intentional imperfections)
- **Drift 📉:** `watch_hours_30d` mean declines across `observation_month` cohorts → non-trivial PSI; makes time-aware split matter.
- **Imbalance ⚖️:** ~8–12% monthly churn (intercept tuned by bisection) → forces lift/PR metrics over accuracy.
- **Missingness ␀:** engagement fields blank for first-month subscribers; `age` ~8% missing.
- **Leakage trap ⚠️:** `cancel_flow_visits_30d` spikes near-perfectly with churn (with noise) — planted for the agent to catch/flag.
- **`cltv`:** derived value (monthly price × expected remaining tenure, from observable engagement — not the label) — feeds the policy simulator.
- **Determinism:** fully seeded — same seed → identical dataset (reproducible tests/regeneration).

## Acceptance tests
- Same seed → identical frame (determinism).
- Churn rate ∈ ~8–12% (imbalance lever).
- `watch_hours_30d` declines first→last cohort (drift lever; PSI check added once the metric core exists in S5).
- Documented missingness present where intended.
- `cancel_flow_visits_30d` strongly separates churners (trap planted).
- Each churner's `churn_next_30d = 1` row is their last (no future leaks; truncation correct).
- All schema columns present with expected dtypes; `(subscriber_id, observation_month)` unique.

## Parameters & output
- **Cohorts:** 24 monthly `observation_month` periods (room for v2 seasonality).
- **Subscribers:** ~8,000 (≈60k subscriber-month rows at defaults; ~0.8 MB parquet).
- **Seed:** configurable; deterministic default (42).
- **Output:** Parquet (default `data/churn_panel.parquet`) + a printed summary (rows, churn rate, null rates, drift feature).

## Column schema (per subscriber-month)
`subscriber_id`, `observation_month`, `signup_month`, `tenure_months`, `plan_tier`,
`monthly_price`, `payment_method`, `on_promo`, `promo_months_left`, `household_profiles`,
`watch_hours_30d`, `active_days_30d`, `days_since_last_watch`, `watch_hours_trend`,
`titles_started_30d`, `titles_completed_30d`, `avg_session_minutes`, `support_tickets_30d`,
`payment_failures_30d`, `age`, `region`, `signup_device`, `cancel_flow_visits_30d`,
`cltv`, `churn_next_30d` (target).
