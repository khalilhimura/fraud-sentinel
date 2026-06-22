from pathlib import Path

import duckdb
import pandas as pd
import pytest

from fraud_demo.ingest import REQUIRED_COLUMNS, SchemaValidationError, ingest_transactions


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def test_ingest_transactions_normalizes_rejects_and_deduplicates(tmp_path: Path):
    source = tmp_path / "transactions.csv"
    _write_csv(
        source,
        [
            {
                "transaction_id": " TX001 ",
                "event_timestamp": "2026-01-01T00:00:00+08:00",
                "sender_account_id": " acc_a ",
                "receiver_account_id": " acc_b ",
                "amount": "100.50",
                "currency": " myr ",
                "sender_country": " my ",
                "receiver_country": " sg ",
            },
            {
                "transaction_id": "TX001",
                "event_timestamp": "2026-01-01T01:00:00+08:00",
                "sender_account_id": "ACC_C",
                "receiver_account_id": "ACC_D",
                "amount": "200.00",
                "currency": "MYR",
            },
            {
                "transaction_id": "TX_BAD_AMOUNT",
                "event_timestamp": "2026-01-01T00:00:00Z",
                "sender_account_id": "ACC_A",
                "receiver_account_id": "ACC_B",
                "amount": "-1",
                "currency": "MYR",
            },
            {
                "transaction_id": "TX_BAD_ID",
                "event_timestamp": "2026-01-01T00:00:00Z",
                "sender_account_id": "",
                "receiver_account_id": "ACC_B",
                "amount": "10",
                "currency": "MYR",
            },
            {
                "transaction_id": "TX_BAD_TIME",
                "event_timestamp": "not-a-date",
                "sender_account_id": "ACC_A",
                "receiver_account_id": "ACC_B",
                "amount": "10",
                "currency": "MYR",
            },
        ],
    )

    result = ingest_transactions([source], run_id="RUN_TEST", artifacts_dir=tmp_path / "artifacts")

    normalized = pd.read_parquet(result.normalized_path)
    rejected = pd.read_parquet(result.rejected_path)
    assert result.duckdb_path.exists()
    with duckdb.connect(str(result.duckdb_path), read_only=True) as connection:
        table_counts = connection.execute(
            """
            select
              (select count(*) from normalized_transactions) as normalized_count,
              (select count(*) from rejected_rows) as rejected_count
            """
        ).fetchone()
    assert table_counts == (1, 4)

    assert result.valid_row_count == 1
    assert result.rejected_row_count == 3
    assert result.duplicate_row_count == 1
    assert result.source_data_fingerprint
    assert len(result.source_data_fingerprint) == 64

    row = normalized.iloc[0].to_dict()
    assert row["transaction_id"] == "TX001"
    assert row["sender_account_id"] == "acc_a"
    assert row["receiver_account_id"] == "acc_b"
    assert row["amount"] == 100.50
    assert row["currency"] == "MYR"
    assert row["sender_country"] == "MY"
    assert row["receiver_country"] == "SG"
    assert row["source_file"] == str(source)
    assert row["source_row_number"] == 2

    assert set(rejected["rejection_code"]) == {
        "duplicate_transaction_id",
        "invalid_amount",
        "missing_required_value",
        "invalid_timestamp",
    }
    assert "raw_values_json" in rejected.columns


def test_ingest_transactions_fails_on_missing_required_column(tmp_path: Path):
    source = tmp_path / "missing.csv"
    rows = [{column: "x" for column in REQUIRED_COLUMNS if column != "amount"}]
    _write_csv(source, rows)

    with pytest.raises(SchemaValidationError, match="amount"):
        ingest_transactions([source], run_id="RUN_MISSING", artifacts_dir=tmp_path / "artifacts")
