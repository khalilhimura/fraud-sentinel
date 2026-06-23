from pathlib import Path

import duckdb
import pytest

from fraud_demo.duckdb_viewer import list_tables, load_table_preview


def _write_sample_db(path: Path) -> None:
    with duckdb.connect(str(path)) as connection:
        connection.execute(
            """
            create table normalized_transactions (
                transaction_id varchar,
                sender_account_id varchar,
                receiver_account_id varchar,
                amount double,
                description varchar
            )
            """
        )
        connection.executemany(
            """
            insert into normalized_transactions values (?, ?, ?, ?, ?)
            """,
            [
                ("TX001", "ACC_A", "ACC_MULE", 125.5, "salary transfer"),
                ("TX002", "ACC_B", "ACC_C", 20.0, "coffee"),
                ("TX003", "ACC_D", "ACC_E", 75.0, "Mule scenario marker"),
            ],
        )
        connection.execute("create table alerts (alert_id varchar, account_id varchar)")


def test_duckdb_viewer_lists_tables_and_filters_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "transactions.duckdb"
    _write_sample_db(db_path)

    assert list_tables(db_path) == ["alerts", "normalized_transactions"]

    preview = load_table_preview(
        db_path,
        "normalized_transactions",
        search="mule",
        limit=50,
    )

    assert preview.total_rows == 3
    assert preview.filtered_rows == 2
    assert preview.returned_rows == 2
    assert set(preview.frame["transaction_id"]) == {"TX001", "TX003"}


def test_duckdb_viewer_rejects_unknown_table(tmp_path: Path) -> None:
    db_path = tmp_path / "transactions.duckdb"
    _write_sample_db(db_path)

    with pytest.raises(ValueError, match="Unknown table"):
        load_table_preview(db_path, "missing_table")
