"""Small helpers for locally previewing generated DuckDB tables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

DEFAULT_SAMPLE_DB_PATH = Path("artifacts/runs/RUN_SAMPLE/transactions.duckdb")
DEFAULT_PREVIEW_LIMIT = 1000
MAX_PREVIEW_LIMIT = 100_000


@dataclass(frozen=True)
class TablePreview:
    """A bounded table preview returned from a local DuckDB artifact."""

    table_name: str
    total_rows: int
    filtered_rows: int
    returned_rows: int
    frame: pd.DataFrame


def quote_identifier(identifier: str) -> str:
    """Quote a DuckDB identifier after rejecting invalid input."""

    if "\x00" in identifier:
        raise ValueError("DuckDB identifiers cannot contain null bytes")
    return '"' + identifier.replace('"', '""') + '"'


def _coerce_limit(limit: int) -> int:
    return min(max(int(limit), 1), MAX_PREVIEW_LIMIT)


def list_tables(db_path: Path | str) -> list[str]:
    """Return user tables in a local DuckDB database."""

    path = Path(db_path)
    with duckdb.connect(str(path), read_only=True) as connection:
        rows = connection.sql("show tables").fetchall()
    return sorted(str(row[0]) for row in rows)


def describe_table(db_path: Path | str, table_name: str) -> pd.DataFrame:
    """Return DuckDB column metadata for a known table."""

    tables = list_tables(db_path)
    if table_name not in tables:
        raise ValueError(f"Unknown table: {table_name}")

    table_ref = quote_identifier(table_name)
    with duckdb.connect(str(db_path), read_only=True) as connection:
        return connection.sql(f"describe {table_ref}").fetchdf()


def load_table_preview(
    db_path: Path | str,
    table_name: str,
    *,
    search: str = "",
    limit: int = DEFAULT_PREVIEW_LIMIT,
) -> TablePreview:
    """Load a bounded, optionally filtered DataFrame from a local DuckDB table."""

    tables = list_tables(db_path)
    if table_name not in tables:
        raise ValueError(f"Unknown table: {table_name}")

    table_ref = quote_identifier(table_name)
    coerced_limit = _coerce_limit(limit)
    search_term = search.strip()

    with duckdb.connect(str(db_path), read_only=True) as connection:
        total_rows = int(connection.sql(f"select count(*) from {table_ref}").fetchone()[0])
        columns = [
            str(row[0])
            for row in connection.sql(f"describe {table_ref}").fetchall()
        ]

        where_sql = ""
        params: list[object] = []
        if search_term and columns:
            where_parts = [
                f"cast({quote_identifier(column)} as varchar) ilike ?"
                for column in columns
            ]
            where_sql = " where " + " or ".join(where_parts)
            params = [f"%{search_term}%"] * len(columns)

        filtered_rows = int(
            connection.execute(
                f"select count(*) from {table_ref}{where_sql}",
                params,
            ).fetchone()[0]
        )
        frame = connection.execute(
            f"select * from {table_ref}{where_sql} limit ?",
            [*params, coerced_limit],
        ).fetchdf()

    return TablePreview(
        table_name=table_name,
        total_rows=total_rows,
        filtered_rows=filtered_rows,
        returned_rows=len(frame),
        frame=frame,
    )
