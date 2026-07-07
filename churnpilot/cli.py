"""churnpilot command-line interface.

Commands are added one slice at a time, following the build order in WORKFLOW.md:
generate -> validate -> profile -> metrics -> split -> train -> compare -> evaluate ->
simulate-policy -> report -> monitor -> dashboard.

Built so far: version, init, generate, validate, profile, metrics, split, train.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .config import CONFIG_TEMPLATE

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="churnpilot — a config-driven churn/retention analysis tool.",
)


@app.callback()
def main() -> None:
    """churnpilot — a config-driven churn/retention analysis tool.

    A callback is defined so Typer keeps subcommand mode even while only one
    command exists; without it, a single-command Typer app treats the command
    name as a stray argument.
    """


@app.command()
def version() -> None:
    """Print the installed churnpilot version."""
    typer.echo(f"churnpilot {__version__}")


@app.command()
def init(
    path: Path = typer.Option(
        Path("churn.yaml"), "--path", help="Where to write the config template."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite the file if it already exists."),
) -> None:
    """Scaffold a churn.yaml config template to point churnpilot at your data."""
    if path.exists() and not force:
        typer.echo(f"{path} already exists — use --force to overwrite.")
        raise typer.Exit(code=1)
    path.write_text(CONFIG_TEMPLATE)
    typer.echo(f"Wrote {path}. Edit it to point churnpilot at your data.")


@app.command()
def generate(
    out: Path = typer.Option(
        Path("data/churn_panel.parquet"), "--out", help="Output parquet path."
    ),
    subscribers: int = typer.Option(8000, "--subscribers", help="Number of subscribers."),
    months: int = typer.Option(24, "--months", help="Number of monthly cohorts."),
    seed: int = typer.Option(42, "--seed", help="RNG seed (deterministic)."),
) -> None:
    """Generate the deterministic synthetic streaming churn panel (no real data)."""
    from .generate import make_panel, summarize

    df = make_panel(n_subscribers=subscribers, n_months=months, seed=seed)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    typer.echo(f"Wrote {out}")
    typer.echo(summarize(df))


def _load(config_path: Path):
    """Load config + data for a command, exiting cleanly (no traceback) on failure."""
    from .config import ConfigError, load_config
    from .source import SourceError, load_data

    try:
        cfg = load_config(config_path)
    except ConfigError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    try:
        df = load_data(cfg)
    except SourceError as exc:
        typer.echo(f"Could not load data: {exc}")
        raise typer.Exit(code=1) from exc
    return cfg, df


@app.command()
def validate(
    config: Path = typer.Option(
        Path("churn.yaml"), "--config", help="Path to the churn.yaml config."
    ),
) -> None:
    """Check that the configured dataset is usable by churnpilot (fails gracefully)."""
    from .validate import validate as run_validate

    cfg, df = _load(config)
    report = run_validate(df, cfg)
    typer.echo(report.render())
    if not report.ok:
        raise typer.Exit(code=1)


@app.command()
def profile(
    config: Path = typer.Option(
        Path("churn.yaml"), "--config", help="Path to the churn.yaml config."
    ),
) -> None:
    """Profile every column of the configured dataset (EDA numbers)."""
    import pandas as pd

    from .profile import high_corr_features, profile_frame

    cfg, df = _load(config)
    records = profile_frame(df, cfg)
    table = pd.DataFrame(records)
    order = [
        "column",
        "role",
        "null_rate",
        "n_unique",
        "target_corr",
        "mean",
        "std",
        "min",
        "q25",
        "q50",
        "q75",
        "max",
    ]
    table = table[[c for c in order if c in table.columns]]

    typer.echo(
        f"Profile of {len(df):,} rows × {df.shape[1]} columns  (target: {cfg.columns.target_col})"
    )
    typer.echo("")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        typer.echo(table.to_string(index=False, na_rep=""))

    leaky = high_corr_features(records, threshold=0.5)
    if leaky:
        typer.echo("")
        hits = ", ".join(f"{c} ({v:+.2f})" for c, v in leaky)
        typer.echo(f"⚠ high target correlation — possible leakage: {hits}")


@app.command()
def metrics(
    score_col: str = typer.Option(..., "--score-col", help="Column to treat as the risk score."),
    config: Path = typer.Option(
        Path("churn.yaml"), "--config", help="Path to the churn.yaml config."
    ),
    reference: Path = typer.Option(
        None, "--reference", help="Optional reference parquet for score PSI (drift)."
    ),
    n_bins: int = typer.Option(10, "--n-bins", help="Number of quantile deciles."),
) -> None:
    """Report discrimination/targeting metrics for a score column vs. the target."""
    import pandas as pd

    from . import metrics as m

    cfg, df = _load(config)
    label = cfg.columns.target_col
    if score_col not in df.columns:
        typer.echo(f"score column {score_col!r} not found in data.")
        raise typer.Exit(code=1)
    y = (df[label] == cfg.columns.positive_value).astype(int)
    s = pd.to_numeric(df[score_col], errors="coerce")

    ks = m.ks_table(y, s, n_bins=n_bins)
    typer.echo(f"Metrics for score '{score_col}' vs target '{label}'  ({len(df):,} rows)")
    typer.echo("")
    typer.echo(f"  ROC-AUC          : {m.roc_auc(y, s):.4f}")
    typer.echo(f"  PR-AUC (AP)      : {m.average_precision(y, s):.4f}")
    typer.echo(f"  KS (decile)      : {ks.ks:.4f}   over {ks.n_bins} deciles")
    typer.echo(f"  top-decile lift  : {m.top_decile_lift(y, s):.3f}x")
    typer.echo(f"  rank-order breaks: {m.rank_order_breaks(y, s, n_bins=n_bins)}   (0 = clean)")

    if reference is not None:
        ref = pd.read_parquet(reference)
        if score_col not in ref.columns:
            typer.echo(f"\n⚠ score column {score_col!r} not in reference — skipping PSI.")
        else:
            val = m.psi(ref[score_col], df[score_col], n_bins=n_bins)
            typer.echo(
                f"\n  score PSI (ref→data): {val:.4f}   (<0.1 stable, 0.1–0.25 moderate, >0.25 major)"
            )


@app.command()
def split(
    strategy: str = typer.Option("time", "--strategy", help="time | grouped | random."),
    config: Path = typer.Option(
        Path("churn.yaml"), "--config", help="Path to the churn.yaml config."
    ),
    out_dir: Path = typer.Option(
        Path("data/splits"), "--out-dir", help="Where to write the splits + manifest."
    ),
    seed: int = typer.Option(42, "--seed", help="RNG seed (grouped/random)."),
) -> None:
    """Split into train/val/test with a leakage guard; writes parquets + a split-manifest."""
    from .split import SplitError, split_dataset

    cfg, df = _load(config)
    try:
        train, val, test, manifest = split_dataset(df, cfg, strategy=strategy, seed=seed)
    except SplitError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    train.to_parquet(out_dir / "train.parquet", index=False)
    val.to_parquet(out_dir / "val.parquet", index=False)
    test.to_parquet(out_dir / "test.parquet", index=False)
    manifest.write_json(out_dir / "split-manifest.json")

    typer.echo(f"Split ({strategy}) → {out_dir}")
    for name, info in (("train", manifest.train), ("val", manifest.val), ("test", manifest.test)):
        typer.echo(f"  {name}: {info.rows:,} rows, churn {info.positive_rate:.1%}")
    lk = manifest.leakage
    if lk.status == "warn":
        typer.echo(
            f"  ⚠ entity leakage: {lk.subscriber_overlap:,} subscribers in BOTH train & test "
            "— use --strategy time"
        )
    else:
        detail = "expected for time split" if strategy == "time" else "subscribers disjoint"
        typer.echo(
            f"  ✔ leakage guard ok ({lk.subscriber_overlap:,} subscriber overlap — {detail})"
        )


@app.command()
def train(
    train: Path = typer.Option(..., "--train", help="Training parquet (a split output)."),
    model: str = typer.Option("logistic", "--model", help="logistic | tree | rf | xgboost."),
    config: Path = typer.Option(
        Path("churn.yaml"), "--config", help="Path to the churn.yaml config."
    ),
    model_out: Path = typer.Option(
        Path("data/model.pkl"), "--model-out", help="Where to persist the fitted model."
    ),
    smote: bool = typer.Option(False, "--smote", help="Oversample the minority class (SMOTE)."),
    calibrate: bool = typer.Option(False, "--calibrate", help="Isotonic probability calibration."),
    tune: bool = typer.Option(False, "--tune", help="Run the hyperparameter search."),
    early_stopping: bool = typer.Option(
        False, "--early-stopping", help="XGBoost early stopping (mode-aware inner-val)."
    ),
    seed: int = typer.Option(42, "--seed", help="RNG seed."),
) -> None:
    """Fit a model from the menu (leakage-safe) and report it against the baseline floor."""
    import pandas as pd

    from .config import ConfigError, load_config
    from .model import ModelError, feature_columns, save_model, train_model
    from .profile import high_corr_features, profile_frame

    try:
        cfg = load_config(config)
    except ConfigError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    df = pd.read_parquet(train)

    # Safety: warn if a feature about to be used looks like leakage (extreme target corr).
    numeric, categorical = feature_columns(df, cfg)
    used = set(numeric) | set(categorical)
    leaky = [
        (c, v) for c, v in high_corr_features(profile_frame(df, cfg), threshold=0.6) if c in used
    ]
    if leaky:
        hits = ", ".join(f"{c} (|corr|={abs(v):.2f})" for c, v in leaky)
        typer.echo(f"⚠ possible leakage in features: {hits} — consider excluding it.\n")

    try:
        estimator, card = train_model(
            df,
            cfg,
            model=model,
            smote=smote,
            calibrate=calibrate,
            tune=tune,
            early_stopping=early_stopping,
            seed=seed,
        )
    except ModelError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    model_out.parent.mkdir(parents=True, exist_ok=True)
    save_model(estimator, model_out)
    card.write_json(model_out.with_suffix(".card.json"))

    tags = "".join(
        t
        for t, on in (
            (" +smote", smote),
            (" +calibrated", calibrate),
            (" +tuned", tune),
            (" +early-stop", early_stopping),
        )
        if on
    )
    tm, bm = card.train_metrics, card.baseline_metrics
    typer.echo(
        f"Trained {model}{tags} on {len(df):,} rows ({card.n_features} features) → {model_out}"
    )
    typer.echo(
        f"  train : AUC {tm['auc']:.4f} | KS {tm['ks']:.4f} | top-decile lift {tm['top_decile_lift']:.2f}x"
    )
    typer.echo(f"  floor : AUC {bm['auc']:.4f}  (majority-class baseline to beat)")


@app.command()
def compare(
    train: Path = typer.Option(..., "--train", help="Training parquet (a split output)."),
    holdout: Path = typer.Option(
        ..., "--holdout", help="Held-out parquet to rank on (e.g. the val split)."
    ),
    config: Path = typer.Option(
        Path("churn.yaml"), "--config", help="Path to the churn.yaml config."
    ),
    models: str = typer.Option("", "--models", help="Comma-separated subset (default: all)."),
    seed: int = typer.Option(42, "--seed", help="RNG seed."),
) -> None:
    """Fit the model shortlist and rank on held-out performance AND stability."""
    import pandas as pd

    from .compare import compare_models
    from .config import ConfigError, load_config
    from .model import MODELS, ModelError

    try:
        cfg = load_config(config)
    except ConfigError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    tr, ho = pd.read_parquet(train), pd.read_parquet(holdout)
    shortlist = [x.strip() for x in models.split(",") if x.strip()] or list(MODELS)
    try:
        rows = compare_models(tr, ho, cfg, models=shortlist, seed=seed)
    except ModelError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    table = pd.DataFrame(rows)
    for col in ("holdout_auc", "holdout_ks", "holdout_pr_auc"):
        table[col] = table[col].round(4)
    table["holdout_lift"] = table["holdout_lift"].round(2)
    table["stable"] = table["stable"].map({True: "✔", False: ""})

    typer.echo(f"Model comparison  ({len(tr):,} train → {len(ho):,} holdout rows)")
    typer.echo("")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        typer.echo(table.to_string(index=False))

    best = rows[0]
    stable = [r for r in rows if r["stable"]]
    typer.echo("")
    typer.echo(f"  best held-out AUC : {best['model']} ({best['holdout_auc']:.4f})")
    if stable:
        pick = min(stable, key=lambda r: r["auc_drop"])
        typer.echo(
            f"  most stable       : {pick['model']} (auc_drop {pick['auc_drop']:+.4f}, "
            f"score-PSI {pick['score_psi']:.3f}) — prefer for a model you'll trust next quarter"
        )
    else:
        typer.echo("  ⚠ none passed the stability gate (auc_drop < 0.05 and score-PSI < 0.2)")


@app.command()
def evaluate(
    model: Path = typer.Option(..., "--model", help="Persisted fitted model (.pkl)."),
    test: Path = typer.Option(..., "--test", help="Held-out parquet to score."),
    config: Path = typer.Option(
        Path("churn.yaml"), "--config", help="Path to the churn.yaml config."
    ),
    reference: Path = typer.Option(
        None, "--reference", help="Optional reference parquet for score-PSI drift."
    ),
    threshold: float = typer.Option(0.5, "--threshold", help="Cutoff for precision/recall/F1."),
    report_out: Path = typer.Option(
        Path("data/eval-report.json"), "--report-out", help="Where to write the eval-report."
    ),
) -> None:
    """Evaluate a saved model on held-out data — the full metric pack + per-segment + drift."""
    import pandas as pd

    from .config import ConfigError, load_config
    from .evaluate import evaluate_model
    from .model import load_model

    try:
        cfg = load_config(config)
    except ConfigError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    est = load_model(model)
    test_df = pd.read_parquet(test)
    ref_df = pd.read_parquet(reference) if reference is not None else None
    try:
        report = evaluate_model(est, test_df, cfg, reference_df=ref_df, threshold=threshold)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    report_out.parent.mkdir(parents=True, exist_ok=True)
    report.write_json(report_out)

    mx = report.metrics
    typer.echo(f"Held-out evaluation  ({report.n_rows:,} rows) → {report_out}")
    typer.echo("")
    typer.echo(
        f"  AUC {mx['auc']:.4f} | PR-AUC {mx['pr_auc']:.4f} | KS {mx['ks']:.4f} | "
        f"top-decile lift {mx['top_decile_lift']:.2f}x | rank-order breaks {mx['rank_order_breaks']}"
    )
    typer.echo(
        f"  @{threshold:g}: precision {mx['precision']:.3f} | recall {mx['recall']:.3f} | "
        f"F1 {mx['f1']:.3f} | log-loss {mx['log_loss']:.4f} | ECE {mx['ece']:.4f}"
    )
    if report.score_psi is not None:
        typer.echo(
            f"  score-PSI (reference→test): {report.score_psi:.4f}   (<0.1 stable, >0.25 major)"
        )

    for col, seg in report.segments.items():
        typer.echo(f"\n  by {col}:")
        for level, s in seg.items():
            auc = f"{s['auc']:.3f}" if s["auc"] is not None else "  n/a"
            typer.echo(
                f"    {level:<12} n={s['n']:>6,}  churn {s['churn_rate']:.1%}  AUC {auc}  lift {s['lift']:.2f}x"
            )


@app.command("simulate-policy")
def simulate_policy_cmd(
    model: Path = typer.Option(..., "--model", help="Persisted fitted model (.pkl)."),
    data: Path = typer.Option(..., "--data", help="Customer parquet to target."),
    config: Path = typer.Option(
        Path("churn.yaml"), "--config", help="Path to the churn.yaml config."
    ),
    save_rate: float = typer.Option(
        0.3, "--save-rate", help="P(offer rescues a would-be churner)."
    ),
    offer_cost: float = typer.Option(5.0, "--offer-cost", help="Cost of one save-offer ($)."),
    budget: Optional[float] = typer.Option(None, "--budget", help="Total offer budget ($)."),
    n_offers: Optional[int] = typer.Option(None, "--n-offers", help="Max number of offers."),
    report_out: Path = typer.Option(
        Path("data/policy-report.json"), "--report-out", help="Where to write the policy-report."
    ),
) -> None:
    """Cost-based retention targeting: whom to save under a budget, and the ROI."""
    import pandas as pd

    from .config import ConfigError, load_config
    from .model import load_model
    from .policy import PolicyError, simulate_policy

    try:
        cfg = load_config(config)
    except ConfigError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    est = load_model(model)
    df = pd.read_parquet(data)
    try:
        report = simulate_policy(
            est,
            df,
            cfg,
            save_rate=save_rate,
            offer_cost=offer_cost,
            budget=budget,
            n_offers=n_offers,
        )
    except PolicyError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    report_out.parent.mkdir(parents=True, exist_ok=True)
    report.write_json(report_out)

    if budget is not None:
        limit = f"${budget:,.0f} budget"
    elif n_offers is not None:
        limit = f"{n_offers:,} offers"
    else:
        limit = "unlimited budget"
    typer.echo(
        f"Retention policy  (save_rate {save_rate:g}, offer ${offer_cost:g}, {limit})  → {report_out}"
    )
    typer.echo("")
    typer.echo(
        f"  target {report.n_targeted:,} of {report.n_eligible:,} profitable "
        f"({report.n_customers:,} customers)"
    )
    roi = f" | ROI {report.roi:.2f}x" if report.roi is not None else ""
    typer.echo(
        f"  retained value ${report.expected_retained_value:,.0f} | "
        f"spend ${report.expected_spend:,.0f} | net ${report.net_value:,.0f}{roi}"
    )
    if report.segments:
        typer.echo("\n  targeted by plan_tier:")
        for level, s in report.segments.items():
            typer.echo(
                f"    {level:<12} {s['n_targeted']:>6,} offers → ${s['retained_value']:,.0f} retained"
            )
    typer.echo(
        f"\n  (save_rate {save_rate:g} is a fixed v1 assumption; uplift modeling replaces it in v2)"
    )


@app.command()
def report(
    eval_report: Path = typer.Option(..., "--eval", help="eval-report.json (from `evaluate`)."),
    policy: Path = typer.Option(
        None, "--policy", help="policy-report.json (from `simulate-policy`)."
    ),
    model_card: Path = typer.Option(None, "--model-card", help="model-card JSON (from `train`)."),
    out: Path = typer.Option(
        Path("data/report.html"), "--out", help="Where to write the HTML report."
    ),
) -> None:
    """Render a shareable, self-contained HTML report from the pipeline artifacts."""
    import json

    from .report import build_html

    ev = json.loads(eval_report.read_text())
    pol = json.loads(policy.read_text()) if policy is not None else None
    mc = json.loads(model_card.read_text()) if model_card is not None else None

    html = build_html(ev, pol, mc)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    typer.echo(f"Wrote {out}  ({len(html):,} bytes) — open it in a browser.")


if __name__ == "__main__":  # pragma: no cover
    app()
