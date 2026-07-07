"""Tests for the data source loader (S3): synthetic / file / sqlite behind one interface."""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from churnpilot.config import ChurnConfig
from churnpilot.source import SourceError, load_data

SCHEMA = {"id_col": "subscriber_id", "target_col": "churn_next_30d"}

SMALL = pd.DataFrame(
    {
        "subscriber_id": [1, 2, 3],
        "churn_next_30d": [0, 1, 0],
        "watch_hours_30d": [5.0, 1.0, 9.0],
    }
)


def _cfg(source: dict) -> ChurnConfig:
    return ChurnConfig.model_validate({"source": source, "schema": SCHEMA})


def test_synthetic_source():
    df = load_data(_cfg({"kind": "synthetic"}))
    assert len(df) > 0
    assert "churn_next_30d" in df.columns


def test_file_parquet(tmp_path):
    p = tmp_path / "data.parquet"
    SMALL.to_parquet(p, index=False)
    out = load_data(_cfg({"kind": "file", "path": str(p)}))
    pd.testing.assert_frame_equal(out, SMALL)


def test_file_csv(tmp_path):
    p = tmp_path / "data.csv"
    SMALL.to_csv(p, index=False)
    out = load_data(_cfg({"kind": "file", "path": str(p)}))
    assert list(out.columns) == list(SMALL.columns)
    assert len(out) == 3


def test_file_missing_raises(tmp_path):
    with pytest.raises(SourceError, match="not found"):
        load_data(_cfg({"kind": "file", "path": str(tmp_path / "nope.parquet")}))


def test_file_bad_extension_raises(tmp_path):
    p = tmp_path / "data.json"
    p.write_text("{}")
    with pytest.raises(SourceError, match="Unsupported file extension"):
        load_data(_cfg({"kind": "file", "path": str(p)}))


def test_sqlite_source(tmp_path):
    dbp = tmp_path / "customers.db"
    con = sqlite3.connect(dbp)
    SMALL.to_sql("customers", con, index=False)
    con.close()
    out = load_data(_cfg({"kind": "sqlite", "dsn": str(dbp), "table": "customers"}))
    assert list(out.columns) == list(SMALL.columns)
    assert len(out) == 3


def test_sqlite_missing_db_raises(tmp_path):
    with pytest.raises(SourceError, match="database not found"):
        load_data(_cfg({"kind": "sqlite", "dsn": str(tmp_path / "nope.db"), "table": "t"}))
