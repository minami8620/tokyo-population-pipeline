"""DuckDB connection with the analytical views defined in ``sql/views.sql``."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import duckdb


def connect(data_dir: Path) -> duckdb.DuckDBPyConnection:
    processed = (Path(data_dir) / "processed").resolve().as_posix()
    sql = files("tokyo_pop").joinpath("sql/views.sql").read_text(encoding="utf-8")
    con = duckdb.connect()
    con.execute(sql.replace("{processed}", processed))
    return con
