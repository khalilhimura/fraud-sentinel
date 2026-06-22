"""Run manifest helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fraud_demo.ingest import IngestionResult


def build_phase2_manifest(
    ingestion: IngestionResult,
    profile_report: dict[str, object],
) -> dict[str, Any]:
    """Build a run manifest for the completed Phase 2 slice."""

    now = datetime.now(UTC).isoformat()
    return {
        "run_id": ingestion.run_id,
        "status": "phase2_complete",
        "started_at": None,
        "completed_at": now,
        "source_files": ingestion.source_files,
        "source_file_fingerprints": ingestion.source_file_fingerprints,
        "source_data_fingerprint": ingestion.source_data_fingerprint,
        "valid_row_count": ingestion.valid_row_count,
        "rejected_row_count": ingestion.rejected_row_count,
        "duplicate_row_count": ingestion.duplicate_row_count,
        "raw_row_count": ingestion.raw_row_count,
        "distinct_account_count": profile_report.get("distinct_account_count", 0),
        "alert_count": 0,
        "cluster_count": 0,
        "rules_config_hash": None,
        "pipeline_config_hash": None,
        "code_commit": "uncommitted",
        "stage_timings_seconds": {},
        "phase_status": {
            "phase2_ingestion_profile": "complete",
            "phase3_features_scoring": "pending",
            "phase4_graph_clusters": "pending",
            "phase5_okf": "pending",
            "phase6_dashboard": "pending",
            "phase7_monitoring": "pending",
        },
        "artifact_paths": {
            "normalized_transactions": str(ingestion.normalized_path),
            "rejected_rows": str(ingestion.rejected_path),
            "duckdb_database": str(ingestion.duckdb_path),
            "data_quality_report": str(profile_report["report_path"]),
            "ingestion_summary": str(ingestion.run_dir / "ingestion_summary.json"),
            "run_manifest": str(ingestion.run_dir / "run_manifest.json"),
        },
    }


def write_run_manifest(run_dir: Path | str, manifest: dict[str, Any]) -> Path:
    """Write `run_manifest.json` into a run directory."""

    manifest_path = Path(run_dir) / "run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def build_phase3_manifest(
    phase2_manifest: dict[str, Any],
    feature_result: Any,
    scoring_result: Any,
    alert_result: Any,
    stage_timings_seconds: dict[str, float],
) -> dict[str, Any]:
    """Extend a Phase 2 manifest with Phase 3 feature, scoring, and alert artifacts."""

    manifest = dict(phase2_manifest)
    artifact_paths = dict(manifest.get("artifact_paths", {}))
    artifact_paths.update(
        {
            "account_features": str(feature_result.account_features_path),
            "account_risk": str(scoring_result.account_risk_path),
            "rule_evidence": str(scoring_result.rule_evidence_path),
            "alerts": str(alert_result.alerts_path),
        }
    )
    phase_status = dict(manifest.get("phase_status", {}))
    phase_status["phase3_features_scoring"] = "complete"

    timings = dict(manifest.get("stage_timings_seconds", {}))
    timings.update(stage_timings_seconds)

    manifest.update(
        {
            "status": "phase3_complete",
            "completed_at": datetime.now(UTC).isoformat(),
            "distinct_account_count": feature_result.account_count,
            "alert_count": alert_result.alert_count,
            "rules_config_hash": scoring_result.rules_config_hash,
            "stage_timings_seconds": timings,
            "phase_status": phase_status,
            "artifact_paths": artifact_paths,
        }
    )
    return manifest
