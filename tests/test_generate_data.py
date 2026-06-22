from pathlib import Path

import pandas as pd

from fraud_demo.config import file_sha256
from fraud_demo.generate_data import generate_synthetic_transactions


def test_generate_synthetic_transactions_writes_required_columns_and_manifest(tmp_path: Path):
    output = tmp_path / "transactions.csv"

    result = generate_synthetic_transactions(rows=250, output=output, seed=7)

    frame = pd.read_csv(output)
    assert len(frame) == 250
    assert result.row_count == 250
    assert result.output_path == output
    assert result.scenario_manifest_path.exists()

    for column in [
        "transaction_id",
        "event_timestamp",
        "sender_account_id",
        "receiver_account_id",
        "amount",
        "currency",
        "device_id",
        "ip_address",
        "is_synthetic_fraud_seed",
        "synthetic_scenario",
    ]:
        assert column in frame.columns

    assert set(result.scenario_counts) >= {
        "fan_in_mule",
        "rapid_pass_through",
        "layering_chain",
        "shared_device_ring",
        "cross_border_funnel",
        "new_account_burst",
        "short_cycle",
    }
    assert frame["is_synthetic_fraud_seed"].sum() > 0


def test_generate_synthetic_transactions_is_reproducible(tmp_path: Path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"

    generate_synthetic_transactions(rows=120, output=first, seed=42)
    generate_synthetic_transactions(rows=120, output=second, seed=42)

    assert file_sha256(first) == file_sha256(second)
