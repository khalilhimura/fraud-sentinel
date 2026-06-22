from pathlib import Path

import pandas as pd

from fraud_demo.features import compute_account_features


def _write_normalized(run_dir: Path, rows: list[dict[str, object]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame["event_timestamp"] = pd.to_datetime(frame["event_timestamp"], utc=True)
    frame.to_parquet(run_dir / "normalized_transactions.parquet", index=False)


def _row(
    transaction_id: str,
    timestamp: str,
    sender: str,
    receiver: str,
    amount: float,
    *,
    sender_country: str = "MY",
    receiver_country: str = "MY",
    device_id: str = "DEV_NORMAL",
    ip_address: str = "10.0.0.1",
    sender_opened: str = "2025-01-01T00:00:00Z",
    receiver_opened: str = "2025-01-01T00:00:00Z",
) -> dict[str, object]:
    return {
        "transaction_id": transaction_id,
        "event_timestamp": timestamp,
        "sender_account_id": sender,
        "receiver_account_id": receiver,
        "amount": amount,
        "currency": "MYR",
        "sender_country": sender_country,
        "receiver_country": receiver_country,
        "device_id": device_id,
        "ip_address": ip_address,
        "sender_account_opened_at": sender_opened,
        "receiver_account_opened_at": receiver_opened,
    }


def test_compute_account_features_writes_account_feature_artifact(tmp_path: Path):
    run_dir = tmp_path / "artifacts" / "runs" / "RUN_FEATURES"
    rows: list[dict[str, object]] = []
    for index in range(10):
        rows.append(
            _row(
                f"TX_IN_{index}",
                f"2026-01-08T08:{index:02d}:00Z",
                f"ACC_SENDER_{index}",
                "ACC_MULE",
                1_000,
            )
        )
    rows.append(
        _row(
            "TX_OUT",
            "2026-01-08T09:00:00Z",
            "ACC_MULE",
            "ACC_OUT",
            8_500,
            receiver_country="SG",
        )
    )
    rows.append(
        _row(
            "TX_NEW",
            "2026-01-08T10:00:00Z",
            "ACC_SOURCE",
            "ACC_NEW",
            250,
            receiver_opened="2026-01-03T00:00:00Z",
        )
    )
    for index in range(6):
        rows.append(
            _row(
                f"TX_SHARED_{index}",
                f"2026-01-08T10:{index:02d}:00Z",
                f"ACC_DEVICE_{index}",
                f"ACC_TARGET_{index}",
                100,
                device_id="DEV_SHARED",
                ip_address="10.9.0.1",
            )
        )
    rows.extend(
        [
            _row("TX_AB", "2026-01-08T11:00:00Z", "ACC_CYCLE_A", "ACC_CYCLE_B", 100),
            _row("TX_BC", "2026-01-08T11:10:00Z", "ACC_CYCLE_B", "ACC_CYCLE_C", 90),
            _row("TX_CA", "2026-01-08T11:20:00Z", "ACC_CYCLE_C", "ACC_CYCLE_A", 80),
        ]
    )
    _write_normalized(run_dir, rows)

    result = compute_account_features(run_dir)

    features = pd.read_parquet(result.account_features_path).set_index("account_id")
    assert result.run_id == "RUN_FEATURES"
    assert result.account_count == len(features)
    assert result.snapshot_timestamp == "2026-01-08T11:20:00+00:00"
    assert features.loc["ACC_MULE", "unique_senders_7d"] == 10
    assert features.loc["ACC_MULE", "incoming_count_24h"] == 10
    assert features.loc["ACC_MULE", "outgoing_count_24h"] == 1
    assert features.loc["ACC_MULE", "pass_through_ratio_7d"] == 0.85
    assert features.loc["ACC_MULE", "hold_time_proxy_minutes"] == 60
    assert features.loc["ACC_MULE", "cross_border_out_ratio_7d"] == 1.0
    assert features.loc["ACC_NEW", "account_age_days"] == 5
    assert features.loc["ACC_DEVICE_0", "shared_device_account_count_30d"] == 6
    assert features.loc["ACC_DEVICE_0", "shared_ip_account_count_30d"] == 6
    assert bool(features.loc["ACC_CYCLE_A", "short_cycle_flag"]) is True


def test_compute_account_features_marks_missing_optional_sources_as_unavailable(tmp_path: Path):
    run_dir = tmp_path / "artifacts" / "runs" / "RUN_MISSING_OPTIONAL"
    _write_normalized(
        run_dir,
        [
            {
                "transaction_id": "TX001",
                "event_timestamp": "2026-01-08T08:00:00Z",
                "sender_account_id": "ACC_A",
                "receiver_account_id": "ACC_B",
                "amount": 100,
                "currency": "MYR",
            }
        ],
    )

    result = compute_account_features(run_dir)

    features = pd.read_parquet(result.account_features_path).set_index("account_id")
    assert pd.isna(features.loc["ACC_A", "cross_border_out_ratio_7d"])
    assert pd.isna(features.loc["ACC_A", "shared_device_account_count_30d"])
    assert pd.isna(features.loc["ACC_A", "shared_ip_account_count_30d"])
    assert pd.isna(features.loc["ACC_A", "account_age_days"])


def test_compute_account_features_uses_vectorizable_hold_time_and_reciprocal_ratio(
    tmp_path: Path,
):
    run_dir = tmp_path / "artifacts" / "runs" / "RUN_FEATURE_VECTORS"
    _write_normalized(
        run_dir,
        [
            _row("TX_IN_DAY1", "2026-01-07T08:00:00Z", "ACC_SRC_1", "ACC_HUB", 100),
            _row("TX_OUT_DAY1", "2026-01-07T08:30:00Z", "ACC_HUB", "ACC_A", 50),
            _row("TX_IN_DAY2", "2026-01-08T09:00:00Z", "ACC_SRC_2", "ACC_HUB", 100),
            _row("TX_OUT_DAY2", "2026-01-08T10:30:00Z", "ACC_HUB", "ACC_B", 50),
            _row("TX_A_BACK", "2026-01-08T11:00:00Z", "ACC_A", "ACC_HUB", 20),
            _row("TX_ONE_WAY", "2026-01-08T12:00:00Z", "ACC_HUB", "ACC_C", 20),
        ],
    )

    result = compute_account_features(run_dir)

    features = pd.read_parquet(result.account_features_path).set_index("account_id")
    assert features.loc["ACC_HUB", "hold_time_proxy_minutes"] == 60
    assert features.loc["ACC_HUB", "reciprocal_transfer_ratio_7d"] == 0.2
