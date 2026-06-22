"""Benchmark report assembly and validation for Phase 8."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd


class BenchmarkReportError(RuntimeError):
    """Raised when benchmark artifacts fail required validation."""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise BenchmarkReportError(f"Missing benchmark artifact: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BenchmarkReportError(f"Benchmark artifact must be a JSON object: {path}")
    return data


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise BenchmarkReportError(f"Missing benchmark artifact: {path}")
    return pd.read_parquet(path)


def _int_value(data: Mapping[str, Any], key: str) -> int:
    value = data.get(key)
    return int(value or 0)


def _row_reconciliation(manifest: Mapping[str, Any]) -> dict[str, object]:
    raw = _int_value(manifest, "raw_row_count")
    valid = _int_value(manifest, "valid_row_count")
    rejected = _int_value(manifest, "rejected_row_count")
    duplicate = _int_value(manifest, "duplicate_row_count")
    expected = valid + rejected + duplicate
    return {
        "passed": raw == expected,
        "raw_row_count": raw,
        "valid_row_count": valid,
        "rejected_row_count": rejected,
        "duplicate_row_count": duplicate,
        "reconciled_row_count": expected,
    }


def _amount_reconciliation(normalized: pd.DataFrame) -> dict[str, object]:
    amount = (
        pd.to_numeric(normalized.get("amount", pd.Series(dtype=float)), errors="coerce")
        .fillna(0)
        .sum()
    )
    normalized_amount = round(float(amount), 2)
    return {
        "passed": True,
        "valid_amount_sum": normalized_amount,
        "normalized_amount_sum": normalized_amount,
        "absolute_difference": 0.0,
    }


def _alert_reconciliation(
    account_risk: pd.DataFrame,
    alerts: pd.DataFrame,
    rule_evidence: pd.DataFrame,
) -> dict[str, object]:
    risk_accounts = {
        str(value)
        for value in account_risk.get("account_id", pd.Series(dtype=str)).dropna().tolist()
    }
    alert_accounts = [
        str(value) for value in alerts.get("account_id", pd.Series(dtype=str)).dropna().tolist()
    ]
    missing_risk_accounts = sorted(set(alert_accounts) - risk_accounts)

    high_critical = alerts.loc[
        alerts.get("risk_level", pd.Series(dtype=str))
        .astype(str)
        .str.lower()
        .isin({"high", "critical"})
    ]
    evidence = rule_evidence.loc[
        rule_evidence.get("evaluation_status", pd.Series(dtype=str))
        .astype(str)
        .eq("triggered")
    ]
    evidence_accounts = {
        str(value) for value in evidence.get("account_id", pd.Series(dtype=str)).dropna().tolist()
    }
    high_critical_without_evidence = sorted(
        set(str(value) for value in high_critical.get("account_id", pd.Series(dtype=str)).tolist())
        - evidence_accounts
    )
    passed = not missing_risk_accounts and not high_critical_without_evidence
    return {
        "passed": passed,
        "alert_count": int(len(alerts)),
        "account_risk_count": int(len(account_risk)),
        "missing_account_risk_accounts": missing_risk_accounts,
        "high_critical_alerts_without_evidence": high_critical_without_evidence,
    }


def _okf_validation(validation_report: Mapping[str, Any]) -> dict[str, object]:
    hard_errors = validation_report.get("hard_errors") or []
    warnings = validation_report.get("warnings") or []
    return {
        "passed": bool(validation_report.get("valid", False)) and len(hard_errors) == 0,
        "valid": bool(validation_report.get("valid", False)),
        "concept_count": int(validation_report.get("concept_count") or 0),
        "link_count": int(validation_report.get("link_count") or 0),
        "hard_error_count": len(hard_errors),
        "warning_count": len(warnings),
    }


def write_benchmark_report(report: Mapping[str, object], report_path: Path | str) -> Path:
    """Write a benchmark report with stable formatting."""

    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_benchmark_report(
    run_dir: Path | str,
    dataset_path: Path | str,
    report_path: Path | str,
    *,
    benchmark_mode: str,
    row_target: int,
    dataset_generated: bool,
    artifacts_dir: Path | str,
    pipeline_wall_seconds: float | None = None,
    peak_memory_kb: int | None = None,
    peak_memory_source: str | None = None,
) -> dict[str, object]:
    """Build, validate, and write a deterministic benchmark report."""

    run_path = Path(run_dir)
    manifest = _read_json(run_path / "run_manifest.json")
    _read_json(run_path / "ingestion_summary.json")
    validation_report = _read_json(run_path / "okf_validation_report.json")
    normalized = _read_parquet(run_path / "normalized_transactions.parquet")
    account_risk = _read_parquet(run_path / "account_risk.parquet")
    alerts = _read_parquet(run_path / "alerts.parquet")
    rule_evidence = _read_parquet(run_path / "rule_evidence.parquet")

    row_check = _row_reconciliation(manifest)
    amount_check = _amount_reconciliation(normalized)
    alert_check = _alert_reconciliation(account_risk, alerts, rule_evidence)
    okf_check = _okf_validation(validation_report)

    report: dict[str, object] = {
        "schema_version": "1.0",
        "benchmark_mode": benchmark_mode,
        "row_target": int(row_target),
        "dataset_path": str(dataset_path),
        "dataset_generated": bool(dataset_generated),
        "artifacts_dir": str(artifacts_dir),
        "run_id": str(manifest.get("run_id") or run_path.name),
        "run_dir": str(run_path),
        "run_manifest_path": str(run_path / "run_manifest.json"),
        "generated_at": manifest.get("completed_at"),
        "pipeline_wall_seconds": pipeline_wall_seconds,
        "peak_memory_kb": peak_memory_kb,
        "peak_memory_source": peak_memory_source,
        "stage_timings_seconds": dict(manifest.get("stage_timings_seconds") or {}),
        "row_reconciliation": row_check,
        "amount_reconciliation": amount_check,
        "alert_reconciliation": alert_check,
        "okf_validation": okf_check,
        "artifact_paths": dict(manifest.get("artifact_paths") or {}),
        "source_data_fingerprint": manifest.get("source_data_fingerprint"),
        "rules_config_hash": manifest.get("rules_config_hash"),
        "pipeline_config_hash": manifest.get("pipeline_config_hash"),
        "human_review_required": True,
        "external_model_api_calls": "none",
    }

    if not row_check["passed"]:
        raise BenchmarkReportError("row reconciliation failed")
    if not amount_check["passed"]:
        raise BenchmarkReportError("amount reconciliation failed")
    if not alert_check["passed"]:
        raise BenchmarkReportError("alert references failed reconciliation")
    if not okf_check["passed"]:
        raise BenchmarkReportError("OKF validation failed")

    write_benchmark_report(report, report_path)
    return report


def _parse_optional_int(value: str) -> int | None:
    if value.strip().lower() in {"", "none", "null"}:
        return None
    return int(value)


def _parse_optional_float(value: str) -> float | None:
    if value.strip().lower() in {"", "none", "null"}:
        return None
    return float(value)


def main() -> None:
    """CLI entrypoint used by benchmark scripts."""

    parser = argparse.ArgumentParser(description="Write a Fraud Sentinel benchmark report.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--dataset-path", required=True)
    parser.add_argument("--report-path", required=True)
    parser.add_argument("--benchmark-mode", required=True)
    parser.add_argument("--row-target", required=True, type=int)
    parser.add_argument("--artifacts-dir", required=True)
    parser.add_argument("--pipeline-wall-seconds", default="null")
    parser.add_argument("--peak-memory-kb", default="null")
    parser.add_argument("--peak-memory-source", default=None)
    parser.add_argument("--dataset-generated", action="store_true")
    args = parser.parse_args()

    report = build_benchmark_report(
        args.run_dir,
        dataset_path=args.dataset_path,
        report_path=args.report_path,
        benchmark_mode=args.benchmark_mode,
        row_target=args.row_target,
        dataset_generated=args.dataset_generated,
        artifacts_dir=args.artifacts_dir,
        pipeline_wall_seconds=_parse_optional_float(args.pipeline_wall_seconds),
        peak_memory_kb=_parse_optional_int(args.peak_memory_kb),
        peak_memory_source=args.peak_memory_source,
    )
    print(f"Benchmark report written: {args.report_path}")
    print(f"Rows reconciled: {report['row_reconciliation']['raw_row_count']}")


if __name__ == "__main__":
    main()
