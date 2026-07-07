"""churnpilot command-line interface.

Commands are added one slice at a time, following the build order in WORKFLOW.md:
generate -> validate -> profile -> metrics -> split -> train -> compare -> evaluate ->
simulate-policy -> report -> monitor -> dashboard.

Built so far: version, init, generate, validate, profile, metrics, split, train.
"""

from __future__ import annotations

from pathlib import Path

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


if __name__ == "__main__":  # pragma: no cover
    app()
