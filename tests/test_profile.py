from pathlib import Path

import pandas as pd

from fraud_demo.ingest import ingest_transactions
from fraud_demo.manifests import build_phase2_manifest, write_run_manifest
from fraud_demo.profile import profile_run


def test_profile_run_writes_data_quality_report(tmp_path: Path):
    source = tmp_path / "transactions.csv"
    pd.DataFrame(
        [
            {
                "transaction_id": "TX001",
                "event_timestamp": "2026-01-01T00:00:00Z",
                "sender_account_id": "ACC_A",
                "receiver_account_id": "ACC_B",
                "amount": "10.50",
                "currency": "MYR",
            },
            {
                "transaction_id": "TX002",
                "event_timestamp": "2026-01-02T00:00:00Z",
                "sender_account_id": "ACC_B",
                "receiver_account_id": "ACC_C",
                "amount": "20",
                "currency": "MYR",
            },
            {
                "transaction_id": "TX003",
                "event_timestamp": "bad",
                "sender_account_id": "ACC_B",
                "receiver_account_id": "ACC_C",
                "amount": "20",
                "currency": "MYR",
            },
        ]
    ).to_csv(source, index=False)
    ingestion = ingest_transactions([source], "RUN_PROFILE", tmp_path / "artifacts")

    report = profile_run(ingestion.run_dir, ingestion.source_data_fingerprint)

    assert report["run_id"] == "RUN_PROFILE"
    assert report["valid_row_count"] == 2
    assert report["rejected_row_count"] == 1
    assert report["distinct_account_count"] == 3
    assert report["total_amount"] == 30.50
    assert report["currency_counts"] == {"MYR": 2}
    assert Path(report["report_path"]).exists()


def test_write_run_manifest_records_phase2_artifacts(tmp_path: Path):
    source = tmp_path / "transactions.csv"
    pd.DataFrame(
        [
            {
                "transaction_id": "TX001",
                "event_timestamp": "2026-01-01T00:00:00Z",
                "sender_account_id": "ACC_A",
                "receiver_account_id": "ACC_B",
                "amount": "10.50",
                "currency": "MYR",
            }
        ]
    ).to_csv(source, index=False)
    ingestion = ingest_transactions([source], "RUN_MANIFEST", tmp_path / "artifacts")
    report = profile_run(ingestion.run_dir, ingestion.source_data_fingerprint)

    manifest = build_phase2_manifest(ingestion, report)
    manifest_path = write_run_manifest(ingestion.run_dir, manifest)

    saved = pd.read_json(manifest_path, typ="series").to_dict()
    assert saved["run_id"] == "RUN_MANIFEST"
    assert saved["status"] == "phase2_complete"
    assert saved["valid_row_count"] == 1
    assert saved["artifact_paths"]["normalized_transactions"].endswith(
        "normalized_transactions.parquet"
    )
