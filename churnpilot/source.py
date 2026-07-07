"""Data source loader — synthetic / file / sqlite / postgres, behind one interface.

The synthetic generator is just one more "source", so churnpilot is built and tested on
fake data and switched to a real database by changing one line of ``churn.yaml``.
:func:`load_data` returns a plain DataFrame regardless of where the data came from.

SQL is kept trivial (``SELECT * FROM <table>``) — per the "SQL is agnostic of logic"
principle, all real compute happens in Python on the extracted frame.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from .config import ChurnConfig, SourceConfig


class SourceError(RuntimeError):
    """Raised when the configured data source cannot be loaded."""


def load_data(config: ChurnConfig) -> pd.DataFrame:
    """Load the dataset described by ``config.source`` into a DataFrame."""
    src = config.source
    if src.kind == "synthetic":
        from .generate import make_panel

        return make_panel()
    if src.kind == "file":
        return _load_file(src)
    if src.kind == "sqlite":
        return _load_sqlite(src)
    if src.kind == "postgres":
        return _load_postgres(src)
    raise SourceError(f"Unknown source kind: {src.kind!r}")  # pragma: no cover


def _load_file(src: SourceConfig) -> pd.DataFrame:
    assert src.path is not None  # guaranteed by config validation
    p = Path(src.path)
    if not p.exists():
        raise SourceError(f"File not found: {p}")
    ext = p.suffix.lower()
    if ext == ".parquet":
        return pd.read_parquet(p)
    if ext in (".csv", ".txt"):
        return pd.read_csv(p)
    raise SourceError(f"Unsupported file extension {ext!r} (use .parquet or .csv): {p}")


def _load_sqlite(src: SourceConfig) -> pd.DataFrame:
    assert src.dsn is not None and src.table is not None  # guaranteed by config validation
    p = Path(src.dsn)
    if not p.exists():
        raise SourceError(f"SQLite database not found: {p}")
    con = sqlite3.connect(p)
    try:
        return pd.read_sql_query(f'SELECT * FROM "{src.table}"', con)
    except Exception as exc:  # noqa: BLE001 — surface any DB error as a clean SourceError
        raise SourceError(f"Could not read table {src.table!r} from {p}: {exc}") from exc
    finally:
        con.close()


def _load_postgres(src: SourceConfig) -> pd.DataFrame:
    assert src.dsn is not None and src.table is not None  # guaranteed by config validation
    try:
        from sqlalchemy import create_engine
    except ImportError as exc:
        raise SourceError(
            "postgres source requires SQLAlchemy — `pip install sqlalchemy psycopg2-binary`"
        ) from exc
    engine = create_engine(src.dsn)
    try:
        return pd.read_sql(f'SELECT * FROM "{src.table}"', engine)
    except Exception as exc:  # noqa: BLE001
        raise SourceError(f"Could not read table {src.table!r}: {exc}") from exc
    finally:
        engine.dispose()
