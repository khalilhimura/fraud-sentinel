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


def build_phase4_manifest(
    phase3_manifest: dict[str, Any],
    graph_result: Any,
    cluster_result: Any,
    stage_timings_seconds: dict[str, float],
) -> dict[str, Any]:
    """Extend a Phase 3 manifest with Phase 4 graph and cluster artifacts."""

    manifest = dict(phase3_manifest)
    artifact_paths = dict(manifest.get("artifact_paths", {}))
    artifact_paths.update(
        {
            "graph_nodes": str(cluster_result.graph_nodes_path),
            "graph_edges": str(cluster_result.graph_edges_path),
            "clusters": str(cluster_result.clusters_path),
        }
    )
    phase_status = dict(manifest.get("phase_status", {}))
    phase_status["phase4_graph_clusters"] = "complete"

    timings = dict(manifest.get("stage_timings_seconds", {}))
    timings.update(stage_timings_seconds)

    manifest.update(
        {
            "status": "phase4_complete",
            "completed_at": datetime.now(UTC).isoformat(),
            "cluster_count": cluster_result.cluster_count,
            "stage_timings_seconds": timings,
            "phase_status": phase_status,
            "artifact_paths": artifact_paths,
        }
    )
    return manifest


def build_phase5_manifest(
    phase4_manifest: dict[str, Any],
    export_result: Any,
    validation_result: Any,
    stage_timings_seconds: dict[str, float],
) -> dict[str, Any]:
    """Extend a Phase 4 manifest with Phase 5 OKF export and validation artifacts."""

    manifest = dict(phase4_manifest)
    artifact_paths = dict(manifest.get("artifact_paths", {}))
    artifact_paths.update(
        {
            "okf_bundle": str(export_result.bundle_path),
            "okf_manifest": str(export_result.okf_manifest_path),
        }
    )
    if validation_result.report_path is not None:
        artifact_paths["okf_validation_report"] = str(validation_result.report_path)

    phase_status = dict(manifest.get("phase_status", {}))
    phase_status["phase5_okf"] = "complete" if validation_result.valid else "failed"

    timings = dict(manifest.get("stage_timings_seconds", {}))
    timings.update(stage_timings_seconds)

    manifest.update(
        {
            "status": "phase5_complete" if validation_result.valid else "phase5_failed",
            "completed_at": datetime.now(UTC).isoformat(),
            "okf_concept_count": export_result.concept_count,
            "okf_account_count": export_result.account_count,
            "okf_alert_count": export_result.alert_count,
            "okf_cluster_count": export_result.cluster_count,
            "okf_validation_valid": bool(validation_result.valid),
            "okf_validation_warning_count": len(validation_result.warnings),
            "okf_validation_hard_error_count": len(validation_result.hard_errors),
            "stage_timings_seconds": timings,
            "phase_status": phase_status,
            "artifact_paths": artifact_paths,
        }
    )
    return manifest


def build_phase7_manifest(
    phase5_manifest: dict[str, Any],
    monitoring_result: Any,
    stage_timings_seconds: dict[str, float],
) -> dict[str, Any]:
    """Extend a Phase 5 manifest with Phase 7 monitoring artifacts."""

    manifest = dict(phase5_manifest)
    artifact_paths = dict(manifest.get("artifact_paths", {}))
    if monitoring_result.processed_state_path is not None:
        artifact_paths["processed_files_state"] = str(monitoring_result.processed_state_path)
    if monitoring_result.monitoring_log_path is not None:
        artifact_paths["monitoring_log"] = str(monitoring_result.monitoring_log_path)
    if monitoring_result.monitoring_summary_path is not None:
        artifact_paths["monitoring_summary"] = str(monitoring_result.monitoring_summary_path)
    if monitoring_result.alert_changes_path is not None:
        artifact_paths["alert_changes"] = str(monitoring_result.alert_changes_path)
    if monitoring_result.okf_log_path is not None:
        artifact_paths["okf_bundle_log"] = str(monitoring_result.okf_log_path)

    phase_status = dict(manifest.get("phase_status", {}))
    phase_status["phase7_monitoring"] = "complete"

    timings = dict(manifest.get("stage_timings_seconds", {}))
    timings.update(stage_timings_seconds)

    manifest.update(
        {
            "status": "phase7_complete",
            "completed_at": datetime.now(UTC).isoformat(),
            "monitoring_run": True,
            "prior_run_id": monitoring_result.prior_run_id,
            "processed_file_count": monitoring_result.processed_file_count,
            "skipped_file_count": monitoring_result.skipped_file_count,
            "failed_file_count": monitoring_result.failed_file_count,
            "new_transaction_count": monitoring_result.new_transaction_count,
            "alert_change_counts": monitoring_result.alert_change_counts,
            "stage_timings_seconds": timings,
            "phase_status": phase_status,
            "artifact_paths": artifact_paths,
        }
    )
    return manifest
