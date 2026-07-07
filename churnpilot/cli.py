"""churnpilot command-line interface.

Commands are added one slice at a time, following the build order in WORKFLOW.md:
config+init+generate -> validate -> profile+metrics -> split -> train -> evaluate ->
simulate-policy -> monitor -> report -> dashboard.

Only `version` exists at setup. Each later command is its own build slice with tests.
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


@app.command()
def validate(
    config: Path = typer.Option(
        Path("churn.yaml"), "--config", help="Path to the churn.yaml config."
    ),
) -> None:
    """Check that the configured dataset is usable by churnpilot (fails gracefully)."""
    from .config import ConfigError, load_config
    from .source import SourceError, load_data
    from .validate import validate as run_validate

    try:
        cfg = load_config(config)
    except ConfigError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    try:
        df = load_data(cfg)
    except SourceError as exc:
        typer.echo(f"Could not load data: {exc}")
        raise typer.Exit(code=1) from exc

    report = run_validate(df, cfg)
    typer.echo(report.render())
    if not report.ok:
        raise typer.Exit(code=1)


if __name__ == "__main__":  # pragma: no cover
    app()
