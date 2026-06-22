import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from fraud_demo.cli import app
from fraud_demo.config import file_sha256
from fraud_demo.monitoring import (
    MonitoringError,
    ProcessedFileRecord,
    compare_alerts,
    discover_inbox_files,
    load_processed_state,
    process_inbox,
    select_eligible_files,
    write_processed_state,
)


def _write_transactions_csv(path: Path, transaction_ids: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, transaction_id in enumerate(transaction_ids):
        rows.append(
            {
                "transaction_id": transaction_id,
                "event_timestamp": f"2026-01-01T00:{index:02d}:00Z",
                "sender_account_id": f"ACC_SRC_{index:03d}",
                "receiver_account_id": f"ACC_DST_{index:03d}",
                "amount": 100 + index,
                "currency": "MYR",
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _state_record(
    path: Path,
    digest: str,
    *,
    status: str,
    run_id: str = "RUN_OLD",
) -> ProcessedFileRecord:
    return ProcessedFileRecord(
        file_path=str(path),
        file_sha256=digest,
        first_seen_at="2026-06-23T00:00:00+00:00",
        processed_at="2026-06-23T00:01:00+00:00",
        run_id=run_id,
        row_count=1,
        status=status,
        error_message=None if status == "completed" else "schema failed",
    )


def _alert(run_id: str, account_id: str, score: int, level: str) -> dict[str, object]:
    return {
        "alert_id": f"ALERT_{run_id}_{account_id}",
        "run_id": run_id,
        "account_id": account_id,
        "risk_score": score,
        "risk_level": level,
        "triggered_rule_ids": ["high_fan_in"],
    }


def test_processed_file_state_creation_and_update(tmp_path):
    path = tmp_path / "processed_files.json"
    record = ProcessedFileRecord(
        file_path="/tmp/transactions_001.csv",
        file_sha256="a" * 64,
        first_seen_at="2026-06-23T00:00:00+00:00",
        processed_at="2026-06-23T00:01:00+00:00",
        run_id="RUN_MONITOR_20260623_000100",
        row_count=2,
        status="completed",
        error_message=None,
    )

    write_processed_state(path, [record])

    assert load_processed_state(path) == [record]


def test_discover_inbox_files_only_returns_transaction_csvs(tmp_path):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    (inbox / "transactions_001.csv").write_text("transaction_id\nTX1\n", encoding="utf-8")
    (inbox / "notes.csv").write_text("ignored\n", encoding="utf-8")
    (inbox / "transactions_002.txt").write_text("ignored\n", encoding="utf-8")

    assert [path.name for path in discover_inbox_files(inbox)] == ["transactions_001.csv"]


def test_completed_file_hash_is_skipped_without_force(tmp_path):
    source = _write_transactions_csv(tmp_path / "incoming" / "transactions_001.csv", ["TX1"])
    digest = file_sha256(source)
    records = [_state_record(source, digest, status="completed")]

    eligible, skipped = select_eligible_files([source], records, force=False)

    assert eligible == []
    assert [item.file_sha256 for item in skipped] == [digest]


def test_force_reprocesses_completed_file_hash(tmp_path):
    source = _write_transactions_csv(tmp_path / "incoming" / "transactions_001.csv", ["TX1"])
    digest = file_sha256(source)
    records = [_state_record(source, digest, status="completed")]

    eligible, skipped = select_eligible_files([source], records, force=True)

    assert [item.path for item in eligible] == [source]
    assert skipped == []


def test_failed_file_hash_is_retryable(tmp_path):
    source = _write_transactions_csv(tmp_path / "incoming" / "transactions_001.csv", ["TX1"])
    digest = file_sha256(source)
    records = [_state_record(source, digest, status="failed")]

    eligible, skipped = select_eligible_files([source], records, force=False)

    assert [item.path for item in eligible] == [source]
    assert skipped == []


def test_monitoring_run_deduplicates_transaction_ids_across_files(tmp_path):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    _write_transactions_csv(inbox / "transactions_001.csv", ["TX_DUP", "TX_KEEP_A"])
    _write_transactions_csv(inbox / "transactions_002.csv", ["TX_DUP", "TX_KEEP_B"])

    result = process_inbox(
        inbox,
        artifacts_dir=tmp_path / "artifacts",
        run_id="RUN_MONITOR_TEST",
        force=False,
    )

    normalized = pd.read_parquet(result.run_dir / "normalized_transactions.parquet")
    rejected = pd.read_parquet(result.run_dir / "rejected_rows.parquet")
    assert sorted(normalized["transaction_id"].tolist()) == [
        "TX_DUP",
        "TX_KEEP_A",
        "TX_KEEP_B",
    ]
    assert "duplicate_transaction_id" in set(rejected["rejection_code"])


def test_monitoring_manifest_records_phase7_fields_and_timings(tmp_path):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    _write_transactions_csv(inbox / "transactions_001.csv", ["TX1", "TX2"])

    result = process_inbox(
        inbox,
        artifacts_dir=tmp_path / "artifacts",
        run_id="RUN_MONITOR_MANIFEST",
    )

    manifest = json.loads((result.run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "phase7_complete"
    assert manifest["phase_status"]["phase7_monitoring"] == "complete"
    assert manifest["processed_file_count"] == 1
    assert manifest["skipped_file_count"] == 0
    assert "monitor_discovery" in manifest["stage_timings_seconds"]
    assert "alert_comparison" in manifest["stage_timings_seconds"]
    assert manifest["artifact_paths"]["processed_files_state"].endswith(
        "processed_files.json"
    )
    assert manifest["artifact_paths"]["alert_changes"].endswith("alert_changes.parquet")
    assert manifest["artifact_paths"]["monitoring_summary"].endswith("monitoring_summary.json")


def test_process_inbox_skips_previously_completed_hash(tmp_path):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    _write_transactions_csv(inbox / "transactions_001.csv", ["TX1"])
    first = process_inbox(inbox, artifacts_dir=tmp_path / "artifacts", run_id="RUN_FIRST")

    second = process_inbox(inbox, artifacts_dir=tmp_path / "artifacts", run_id="RUN_SECOND")

    assert first.run_created is True
    assert second.run_created is False
    assert second.processed_file_count == 0
    assert second.skipped_file_count == 1
    assert second.run_dir is None


def test_process_inbox_force_reprocesses_completed_hash(tmp_path):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    _write_transactions_csv(inbox / "transactions_001.csv", ["TX1"])
    process_inbox(inbox, artifacts_dir=tmp_path / "artifacts", run_id="RUN_FIRST")

    result = process_inbox(
        inbox,
        artifacts_dir=tmp_path / "artifacts",
        run_id="RUN_FORCE",
        force=True,
    )

    state = load_processed_state(tmp_path / "artifacts" / "monitoring" / "processed_files.json")
    completed_run_ids = [record.run_id for record in state if record.status == "completed"]
    assert result.run_created is True
    assert completed_run_ids == ["RUN_FIRST", "RUN_FORCE"]


def test_process_inbox_records_failed_file_and_keeps_it_retryable(tmp_path):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    bad = inbox / "transactions_bad.csv"
    bad.write_text("wrong\nvalue\n", encoding="utf-8")

    with pytest.raises(MonitoringError):
        process_inbox(inbox, artifacts_dir=tmp_path / "artifacts", run_id="RUN_BAD")

    state = load_processed_state(tmp_path / "artifacts" / "monitoring" / "processed_files.json")
    assert state[-1].status == "failed"
    assert state[-1].error_message
    eligible, skipped = select_eligible_files([bad], state, force=False)
    assert [item.path for item in eligible] == [bad]
    assert skipped == []


def test_alert_comparison_categories():
    prior = pd.DataFrame(
        [
            _alert("RUN_OLD", "ACC_STABLE", 55, "High"),
            _alert("RUN_OLD", "ACC_UP", 55, "High"),
            _alert("RUN_OLD", "ACC_DOWN", 85, "Critical"),
            _alert("RUN_OLD", "ACC_RESOLVED", 55, "High"),
        ]
    )
    current = pd.DataFrame(
        [
            _alert("RUN_NEW", "ACC_BRAND_NEW", 55, "High"),
            _alert("RUN_NEW", "ACC_STABLE", 55, "High"),
            _alert("RUN_NEW", "ACC_UP", 85, "Critical"),
            _alert("RUN_NEW", "ACC_DOWN", 55, "High"),
        ]
    )

    changes = compare_alerts(prior, current, run_id="RUN_NEW", prior_run_id="RUN_OLD")

    assert changes.set_index("account_id")["change_category"].to_dict() == {
        "ACC_BRAND_NEW": "new",
        "ACC_DOWN": "severity_decreased",
        "ACC_RESOLVED": "resolved_below_threshold",
        "ACC_STABLE": "unchanged",
        "ACC_UP": "severity_increased",
    }
    assert changes["human_review_note"].str.contains("requires human review").all()


def test_okf_monitoring_log_is_appended(tmp_path):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    _write_transactions_csv(inbox / "transactions_001.csv", ["TX1"])

    result = process_inbox(inbox, artifacts_dir=tmp_path / "artifacts", run_id="RUN_LOG")

    log_path = tmp_path / "artifacts" / "monitoring" / "monitoring_log.jsonl"
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert entries[-1]["run_id"] == "RUN_LOG"
    assert "alert_change_counts" in entries[-1]
    assert result.okf_log_path is not None
    assert result.okf_log_path.exists()
    assert "Monitoring update" in result.okf_log_path.read_text(encoding="utf-8")


def test_cli_monitor_success_outputs_paths(tmp_path):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    _write_transactions_csv(inbox / "transactions_001.csv", ["TX1", "TX2"])

    result = CliRunner().invoke(
        app,
        ["monitor", "--inbox", str(inbox), "--artifacts-dir", str(tmp_path / "artifacts")],
    )

    assert result.exit_code == 0
    assert "Monitoring complete" in result.output
    assert "processed_files.json" in result.output
    assert "alert_changes.parquet" in result.output


def test_cli_monitor_failure_returns_non_zero_for_bad_file(tmp_path):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    (inbox / "transactions_bad.csv").write_text("wrong\nvalue\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        ["monitor", "--inbox", str(inbox), "--artifacts-dir", str(tmp_path / "artifacts")],
    )

    assert result.exit_code != 0
    assert "Monitoring failed" in result.output
