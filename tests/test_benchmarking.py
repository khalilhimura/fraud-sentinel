import json
from pathlib import Path

import pandas as pd
import pytest

from fraud_demo.benchmarking import BenchmarkReportError, build_benchmark_report


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_benchmark_run(tmp_path: Path) -> Path:
    artifacts_dir = tmp_path / "artifacts"
    run_dir = artifacts_dir / "runs" / "RUN_BENCH"
    run_dir.mkdir(parents=True)
    (tmp_path / "transactions.csv").write_text(
        "transaction_id\nTX1\nTX2\nTX_BAD\n",
        encoding="utf-8",
    )

    manifest = {
        "run_id": "RUN_BENCH",
        "status": "phase5_complete",
        "raw_row_count": 3,
        "valid_row_count": 2,
        "rejected_row_count": 1,
        "duplicate_row_count": 0,
        "source_data_fingerprint": "f" * 64,
        "rules_config_hash": "r" * 64,
        "pipeline_config_hash": "p" * 64,
        "stage_timings_seconds": {"feature_engineering": 0.1, "okf_validate": 0.2},
        "artifact_paths": {"okf_bundle": "artifacts/okf_bundle"},
    }
    _write_json(run_dir / "run_manifest.json", manifest)
    _write_json(
        run_dir / "ingestion_summary.json",
        {
            "run_id": "RUN_BENCH",
            "raw_row_count": 3,
            "valid_row_count": 2,
            "rejected_row_count": 1,
            "duplicate_row_count": 0,
        },
    )
    _write_json(
        run_dir / "okf_validation_report.json",
        {
            "valid": True,
            "concept_count": 2,
            "link_count": 1,
            "hard_errors": [],
            "warnings": [],
        },
    )
    pd.DataFrame(
        [
            {"transaction_id": "TX1", "amount": 10.5},
            {"transaction_id": "TX2", "amount": 20.0},
        ]
    ).to_parquet(run_dir / "normalized_transactions.parquet", index=False)
    pd.DataFrame([{"rejection_code": "invalid_amount"}]).to_parquet(
        run_dir / "rejected_rows.parquet",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "account_id": "ACC_ALERT",
                "risk_score": 55,
                "risk_level": "High",
            },
            {
                "account_id": "ACC_LOW",
                "risk_score": 5,
                "risk_level": "Low",
            },
        ]
    ).to_parquet(run_dir / "account_risk.parquet", index=False)
    pd.DataFrame(
        [
            {
                "alert_id": "ALERT_RUN_BENCH_ACC_ALERT",
                "account_id": "ACC_ALERT",
                "risk_score": 55,
                "risk_level": "High",
                "triggered_rule_ids": ["high_fan_in"],
            }
        ]
    ).to_parquet(run_dir / "alerts.parquet", index=False)
    pd.DataFrame(
        [
            {
                "account_id": "ACC_ALERT",
                "rule_id": "high_fan_in",
                "evaluation_status": "triggered",
            }
        ]
    ).to_parquet(run_dir / "rule_evidence.parquet", index=False)
    return run_dir


def test_build_benchmark_report_records_required_fields(tmp_path):
    run_dir = _write_benchmark_run(tmp_path)

    report = build_benchmark_report(
        run_dir,
        dataset_path=tmp_path / "transactions.csv",
        report_path=tmp_path / "benchmark_report.json",
        benchmark_mode="smoke",
        row_target=3,
        dataset_generated=True,
        artifacts_dir=tmp_path / "artifacts",
        pipeline_wall_seconds=1.23,
        peak_memory_kb=123456,
        peak_memory_source="test",
    )

    assert report["schema_version"] == "1.0"
    assert report["run_id"] == "RUN_BENCH"
    assert report["row_reconciliation"]["passed"] is True
    assert report["amount_reconciliation"]["passed"] is True
    assert report["alert_reconciliation"]["passed"] is True
    assert report["okf_validation"]["passed"] is True
    assert report["human_review_required"] is True
    assert report["external_model_api_calls"] == "none"


def test_build_benchmark_report_fails_row_reconciliation(tmp_path):
    run_dir = _write_benchmark_run(tmp_path)
    manifest_path = run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["raw_row_count"] = 99
    _write_json(manifest_path, manifest)

    with pytest.raises(BenchmarkReportError, match="row reconciliation"):
        build_benchmark_report(
            run_dir,
            dataset_path=tmp_path / "transactions.csv",
            report_path=tmp_path / "benchmark_report.json",
            benchmark_mode="smoke",
            row_target=3,
            dataset_generated=False,
            artifacts_dir=tmp_path / "artifacts",
        )


def test_build_benchmark_report_fails_alert_without_risk_row(tmp_path):
    run_dir = _write_benchmark_run(tmp_path)
    alerts = pd.read_parquet(run_dir / "alerts.parquet")
    alerts.loc[0, "account_id"] = "ACC_MISSING"
    alerts.to_parquet(run_dir / "alerts.parquet", index=False)

    with pytest.raises(BenchmarkReportError, match="alert references"):
        build_benchmark_report(
            run_dir,
            dataset_path=tmp_path / "transactions.csv",
            report_path=tmp_path / "benchmark_report.json",
            benchmark_mode="smoke",
            row_target=3,
            dataset_generated=False,
            artifacts_dir=tmp_path / "artifacts",
        )


def test_build_benchmark_report_fails_okf_hard_errors(tmp_path):
    run_dir = _write_benchmark_run(tmp_path)
    report_path = run_dir / "okf_validation_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["valid"] = False
    report["hard_errors"] = [{"code": "missing_type", "path": "accounts/A.md"}]
    _write_json(report_path, report)

    with pytest.raises(BenchmarkReportError, match="OKF validation"):
        build_benchmark_report(
            run_dir,
            dataset_path=tmp_path / "transactions.csv",
            report_path=tmp_path / "benchmark_report.json",
            benchmark_mode="smoke",
            row_target=3,
            dataset_generated=False,
            artifacts_dir=tmp_path / "artifacts",
        )


def test_benchmark_script_and_makefile_expose_smoke_mode():
    script = Path("scripts/benchmark.sh").read_text(encoding="utf-8")
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "BENCHMARK_ROWS" in script
    assert "BENCHMARK_REPORT" in script
    assert "fraud_demo.benchmarking" in script
    assert "benchmark-smoke:" in makefile
    assert "BENCHMARK_ROWS=1000" in makefile


def test_demo_scripts_makefile_and_readme_document_operating_flow():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert Path("scripts/demo_monitor_delta.sh").exists()
    assert "RUN_SAMPLE" in Path("scripts/demo_run.sh").read_text(encoding="utf-8")
    assert "validate-okf" in Path("scripts/demo_run.sh").read_text(encoding="utf-8")
    assert "demo-prepare:" in makefile
    assert "demo-monitor:" in makefile
    assert "Fallback artifact flow" in readme
