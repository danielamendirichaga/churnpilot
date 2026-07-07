"""Tests for charts + the HTML report (S11)."""

from __future__ import annotations

from churnpilot import charts
from churnpilot.report import build_html

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

GAIN = [{"cum_pop": 0.1 * i, "cum_capture": min(1.0, 0.25 * i)} for i in range(1, 11)]
CALIB = [{"mean_pred": 0.1 * i, "obs_rate": 0.1 * i + 0.02} for i in range(10)]
SEGMENT = {"Basic": {"lift": 1.8}, "Standard": {"lift": 1.9}, "Premium": {"lift": 2.3}}
CURVE = [
    {"n_targeted": k, "spend": k * 3, "retained_value": k * 5.0, "net": k * 2.0}
    for k in (100, 250, 500)
]


# --- charts return valid PNG bytes --------------------------------------- #
def test_charts_return_png():
    assert charts.gain_chart(GAIN).startswith(PNG_MAGIC)
    assert charts.calibration_chart(CALIB).startswith(PNG_MAGIC)
    assert charts.segment_lift_chart(SEGMENT, "plan_tier").startswith(PNG_MAGIC)
    assert charts.policy_tradeoff_chart(CURVE).startswith(PNG_MAGIC)


# --- report assembly ----------------------------------------------------- #
def _eval_report():
    return {
        "n_rows": 11592,
        "metrics": {"auc": 0.655, "top_decile_lift": 1.92, "ks": 0.219, "ece": 0.013},
        "calibration": CALIB,
        "gain": GAIN,
        "segments": {"plan_tier": SEGMENT},
    }


def _policy_report():
    return {"net_value": 32767.0, "roi": 2.37, "tradeoff_curve": CURVE}


def test_report_is_self_contained_html():
    html = build_html(_eval_report(), _policy_report(), {"model_family": "xgboost"})
    assert html.startswith("<!doctype html>")
    assert "</html>" in html
    # Charts are embedded, not linked (shareable, no external assets).
    assert "data:image/png;base64," in html
    assert "http://" not in html and "https://" not in html
    # Headline numbers surface.
    assert "0.655" in html and "$32,767" in html and "xgboost" in html


def test_report_counts_four_figures_with_policy():
    html = build_html(_eval_report(), _policy_report(), None)
    assert html.count("<figure>") == 4  # gain + calibration + segment + policy


def test_report_without_policy_drops_policy_chart():
    html = build_html(_eval_report(), None, None)
    assert html.count("<figure>") == 3
    assert "ECE" in html  # falls back to KS/ECE tiles when no policy


def test_report_from_real_artifacts():
    import pandas as pd  # noqa: F401

    from churnpilot.config import ChurnConfig
    from churnpilot.evaluate import evaluate_model
    from churnpilot.generate import make_panel
    from churnpilot.model import train_model
    from churnpilot.policy import simulate_policy

    schema = {
        "id_col": "subscriber_id",
        "target_col": "churn_next_30d",
        "date_col": "observation_month",
        "value_col": "cltv",
        "features": ["tenure_months", "watch_hours_30d", "days_since_last_watch", "plan_tier"],
    }
    cfg = ChurnConfig.model_validate({"source": {"kind": "synthetic"}, "schema": schema})
    train = make_panel(n_subscribers=800, n_months=8, seed=51)
    test = make_panel(n_subscribers=400, n_months=8, seed=52)
    est, _ = train_model(train, cfg, model="logistic", seed=1)
    ev = evaluate_model(est, test, cfg).model_dump()
    pol = simulate_policy(est, test, cfg, offer_cost=2.0).model_dump()
    html = build_html(ev, pol, None)
    assert html.startswith("<!doctype html>") and html.count("<figure>") == 4
