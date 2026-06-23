"""Standalone Streamlit viewer for generated DuckDB run artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    for candidate in (PROJECT_ROOT, PROJECT_ROOT / "src"):
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))

import duckdb  # noqa: E402
import streamlit as st  # noqa: E402

from fraud_demo.duckdb_viewer import (  # noqa: E402
    DEFAULT_PREVIEW_LIMIT,
    DEFAULT_SAMPLE_DB_PATH,
    MAX_PREVIEW_LIMIT,
    describe_table,
    list_tables,
    load_table_preview,
)


def _default_table_index(tables: list[str]) -> int:
    if "normalized_transactions" in tables:
        return tables.index("normalized_transactions")
    return 0


def render_viewer() -> None:
    st.set_page_config(page_title="DuckDB Table Viewer", layout="wide")
    st.title("DuckDB Table Viewer")
    st.caption("Local-only preview for prepared Fraud Sentinel run artifacts.")

    db_input = st.text_input("DuckDB file", value=str(DEFAULT_SAMPLE_DB_PATH))
    db_path = Path(db_input).expanduser()
    if not db_path.exists():
        st.error(f"File not found: {db_path}")
        return

    try:
        tables = list_tables(db_path)
    except duckdb.Error as exc:
        st.error(f"Could not open DuckDB file: {exc}")
        return

    if not tables:
        st.info("No tables were found in this DuckDB file.")
        return

    table_name = st.selectbox(
        "Table",
        tables,
        index=_default_table_index(tables),
    )
    controls = st.columns([3, 1])
    search = controls[0].text_input("Search all columns", value="")
    limit = controls[1].number_input(
        "Rows",
        min_value=1,
        max_value=MAX_PREVIEW_LIMIT,
        value=DEFAULT_PREVIEW_LIMIT,
        step=500,
    )

    try:
        preview = load_table_preview(
            db_path,
            table_name,
            search=search,
            limit=int(limit),
        )
        columns = describe_table(db_path, table_name)
    except (duckdb.Error, ValueError) as exc:
        st.error(f"Could not load table: {exc}")
        return

    metrics = st.columns(3)
    metrics[0].metric("Total rows", f"{preview.total_rows:,}")
    metrics[1].metric("Matching rows", f"{preview.filtered_rows:,}")
    metrics[2].metric("Shown rows", f"{preview.returned_rows:,}")

    st.dataframe(preview.frame, use_container_width=True, hide_index=True)
    st.download_button(
        "Download shown rows",
        data=preview.frame.to_csv(index=False).encode("utf-8"),
        file_name=f"{preview.table_name}_preview.csv",
        mime="text/csv",
    )

    with st.expander("Columns"):
        st.dataframe(columns, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    render_viewer()
