"""File-based micro-batch monitoring for Phase 7."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from fraud_demo.alerts import generate_alerts
from fraud_demo.clusters import identify_clusters
from fraud_demo.config import canonical_yaml_hash, file_sha256
from fraud_demo.features import compute_account_features
from fraud_demo.graph_builder import build_graph_artifacts
from fraud_demo.ingest import ingest_transactions
from fraud_demo.manifests import (
    build_phase2_manifest,
    build_phase3_manifest,
    build_phase4_manifest,
    build_phase5_manifest,
    build_phase7_manifest,
    write_run_manifest,
)
from fraud_demo.okf_exporter import export_okf_bundle
from fraud_demo.okf_validator import validate_okf_bundle
from fraud_demo.profile import profile_run
from fraud_demo.scoring import score_accounts

PROCESSED_STATE_NAME = "processed_files.json"
MONITORING_LOG_NAME = "monitoring_log.jsonl"
MONITORING_SUMMARY_NAME = "monitoring_summary.json"
ALERT_CHANGES_NAME = "alert_changes.parquet"

COMPLETED_STATUS = "completed"
FAILED_STATUS = "failed"

SEVERITY_RANK = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
ALERT_CHANGE_COLUMNS = [
    "run_id",
    "prior_run_id",
    "account_id",
    "change_category",
    "prior_alert_id",
    "current_alert_id",
    "prior_risk_level",
    "current_risk_level",
    "prior_risk_score",
    "current_risk_score",
    "prior_triggered_rule_ids",
    "current_triggered_rule_ids",
    "human_review_note",
    "created_at",
]


class MonitoringError(RuntimeError):
    """Raised when a monitoring run cannot complete safely."""


@dataclass(frozen=True)
class ProcessedFileRecord:
    """One processed-file state row."""

    file_path: str
    file_sha256: str
    first_seen_at: str
    processed_at: str | None
    run_id: str | None
    row_count: int
    status: str
    error_message: str | None


@dataclass(frozen=True)
class InboxFile:
    """An inbox file with deterministic fingerprint metadata."""

    path: Path
    file_sha256: str
    first_seen_at: str


@dataclass(frozen=True)
class PriorRun:
    """Latest successful analytical run available for comparison."""

    run_id: str
    run_dir: Path
    manifest: dict[str, Any]


@dataclass(frozen=True)
class MonitoringResult:
    """Outcome and artifacts from a monitor command."""

    run_id: str | None
    run_dir: Path | None
    run_created: bool
    prior_run_id: str | None
    processed_file_count: int
    skipped_file_count: int
    failed_file_count: int
    new_transaction_count: int
    alert_change_counts: dict[str, int]
    processed_state_path: Path
    monitoring_log_path: Path
    monitoring_summary_path: Path | None
    alert_changes_path: Path | None
    manifest_path: Path | None
    okf_log_path: Path | None
    stage_timings_seconds: dict[str, float]
    output_paths: dict[str, Path]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _generated_run_id() -> str:
    return f"RUN_MONITOR_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"


def _monitoring_dir(artifacts_dir: Path | str) -> Path:
    return Path(artifacts_dir) / "monitoring"


def _state_path(artifacts_dir: Path | str) -> Path:
    return _monitoring_dir(artifacts_dir) / PROCESSED_STATE_NAME


def _log_path(artifacts_dir: Path | str) -> Path:
    return _monitoring_dir(artifacts_dir) / MONITORING_LOG_NAME


def _record_from_dict(data: dict[str, Any]) -> ProcessedFileRecord:
    return ProcessedFileRecord(
        file_path=str(data.get("file_path") or ""),
        file_sha256=str(data.get("file_sha256") or ""),
        first_seen_at=str(data.get("first_seen_at") or ""),
        processed_at=str(data["processed_at"]) if data.get("processed_at") is not None else None,
        run_id=str(data["run_id"]) if data.get("run_id") is not None else None,
        row_count=int(data.get("row_count") or 0),
        status=str(data.get("status") or ""),
        error_message=(
            str(data["error_message"]) if data.get("error_message") is not None else None
        ),
    )


def load_processed_state(path: Path | str) -> list[ProcessedFileRecord]:
    """Load processed-file state from JSON."""

    state_path = Path(path)
    if not state_path.exists():
        return []
    data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise MonitoringError(f"Processed-file state must be a JSON list: {state_path}")
    return [_record_from_dict(item) for item in data if isinstance(item, dict)]


def write_processed_state(
    path: Path | str,
    records: Sequence[ProcessedFileRecord],
) -> Path:
    """Write processed-file state deterministically."""

    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(record) for record in records]
    state_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return state_path


def discover_inbox_files(inbox: Path | str) -> list[Path]:
    """Discover deterministic monitoring inputs."""

    inbox_path = Path(inbox)
    if not inbox_path.exists() or not inbox_path.is_dir():
        raise MonitoringError(f"Inbox directory does not exist: {inbox_path}")
    return sorted(path for path in inbox_path.glob("transactions_*.csv") if path.is_file())


def _first_seen_for_hash(records: Sequence[ProcessedFileRecord], digest: str) -> str:
    seen = sorted(record.first_seen_at for record in records if record.file_sha256 == digest)
    return seen[0] if seen else _now()


def select_eligible_files(
    files: Sequence[Path],
    records: Sequence[ProcessedFileRecord],
    *,
    force: bool = False,
) -> tuple[list[InboxFile], list[InboxFile]]:
    """Split inbox files into eligible and skipped by completed SHA-256 hash."""

    completed_hashes = {
        record.file_sha256 for record in records if record.status == COMPLETED_STATUS
    }
    eligible: list[InboxFile] = []
    skipped: list[InboxFile] = []
    for path in sorted(Path(file_path) for file_path in files):
        digest = file_sha256(path)
        inbox_file = InboxFile(
            path=path,
            file_sha256=digest,
            first_seen_at=_first_seen_for_hash(records, digest),
        )
        if not force and digest in completed_hashes:
            skipped.append(inbox_file)
        else:
            eligible.append(inbox_file)
    return eligible, skipped


def _count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        line_count = sum(1 for _line in handle)
    return max(line_count - 1, 0)


def _latest_successful_run(
    artifacts_dir: Path,
    *,
    exclude_run_id: str | None,
) -> PriorRun | None:
    runs_dir = artifacts_dir / "runs"
    if not runs_dir.exists():
        return None
    candidates: list[tuple[str, float, str, Path, dict[str, Any]]] = []
    for manifest_path in runs_dir.glob("*/run_manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        run_id = str(manifest.get("run_id") or manifest_path.parent.name)
        if run_id == exclude_run_id:
            continue
        if manifest.get("status") not in {"phase5_complete", "phase7_complete"}:
            continue
        candidates.append(
            (
                str(manifest.get("completed_at") or ""),
                manifest_path.stat().st_mtime,
                run_id,
                manifest_path.parent,
                manifest,
            )
        )
    if not candidates:
        return None
    _completed_at, _mtime, run_id, run_dir, manifest = sorted(candidates)[-1]
    return PriorRun(run_id=run_id, run_dir=run_dir, manifest=manifest)


def _write_prior_snapshot(prior_run: PriorRun, artifacts_dir: Path, run_id: str) -> Path | None:
    normalized_path = prior_run.run_dir / "normalized_transactions.parquet"
    if not normalized_path.exists():
        return None
    snapshot_dir = _monitoring_dir(artifacts_dir) / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{run_id}_prior_snapshot.csv"
    frame = pd.read_parquet(normalized_path)
    frame.to_csv(snapshot_path, index=False)
    return snapshot_path


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if hasattr(value, "tolist"):
        return [str(item) for item in value.tolist()]
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        if not value:
            return []
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        if isinstance(loaded, list):
            return [str(item) for item in loaded]
        return [str(loaded)]
    return [str(value)]


def _alert_by_account(alerts: pd.DataFrame) -> dict[str, pd.Series]:
    if alerts.empty or "account_id" not in alerts.columns:
        return {}
    frame = alerts.copy()
    frame["risk_score_sort"] = pd.to_numeric(
        frame.get("risk_score"),
        errors="coerce",
    ).fillna(0)
    frame["risk_level_sort"] = (
        frame.get("risk_level", pd.Series(dtype=str)).map(SEVERITY_RANK).fillna(0)
    )
    frame = frame.sort_values(
        ["account_id", "risk_level_sort", "risk_score_sort", "alert_id"],
        ascending=[True, False, False, True],
        kind="mergesort",
    )
    return {
        str(row["account_id"]): row
        for _, row in frame.drop_duplicates(subset=["account_id"], keep="first").iterrows()
    }


def _severity_rank(value: Any) -> int:
    return SEVERITY_RANK.get(str(value), 0)


def _score(value: Any) -> int | None:
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return int(pd.to_numeric(value, errors="coerce"))


def _change_category(prior: pd.Series | None, current: pd.Series | None) -> str:
    if prior is None and current is not None:
        return "new"
    if prior is not None and current is None:
        return "resolved_below_threshold"
    if prior is None or current is None:
        return "unchanged"
    prior_rank = _severity_rank(prior.get("risk_level"))
    current_rank = _severity_rank(current.get("risk_level"))
    if current_rank > prior_rank:
        return "severity_increased"
    if current_rank < prior_rank:
        return "severity_decreased"
    return "unchanged"


def compare_alerts(
    prior_alerts: pd.DataFrame,
    current_alerts: pd.DataFrame,
    *,
    run_id: str,
    prior_run_id: str | None,
) -> pd.DataFrame:
    """Compare account alert state between two analytical snapshots."""

    prior_by_account = _alert_by_account(prior_alerts)
    current_by_account = _alert_by_account(current_alerts)
    created_at = _now()
    records: list[dict[str, object]] = []
    for account_id in sorted(set(prior_by_account) | set(current_by_account)):
        prior = prior_by_account.get(account_id)
        current = current_by_account.get(account_id)
        records.append(
            {
                "run_id": run_id,
                "prior_run_id": prior_run_id,
                "account_id": account_id,
                "change_category": _change_category(prior, current),
                "prior_alert_id": None if prior is None else prior.get("alert_id"),
                "current_alert_id": None if current is None else current.get("alert_id"),
                "prior_risk_level": None if prior is None else prior.get("risk_level"),
                "current_risk_level": None if current is None else current.get("risk_level"),
                "prior_risk_score": None if prior is None else _score(prior.get("risk_score")),
                "current_risk_score": (
                    None if current is None else _score(current.get("risk_score"))
                ),
                "prior_triggered_rule_ids": (
                    [] if prior is None else _as_list(prior.get("triggered_rule_ids"))
                ),
                "current_triggered_rule_ids": (
                    [] if current is None else _as_list(current.get("triggered_rule_ids"))
                ),
                "human_review_note": (
                    "Alert change is a suspicious indicator that requires human review; "
                    "it is not a confirmed fraud determination."
                ),
                "created_at": created_at,
            }
        )
    return pd.DataFrame(records, columns=ALERT_CHANGE_COLUMNS)


def _read_alerts(run_dir: Path | None) -> pd.DataFrame:
    if run_dir is None:
        return pd.DataFrame()
    alerts_path = run_dir / "alerts.parquet"
    if not alerts_path.exists():
        return pd.DataFrame()
    return pd.read_parquet(alerts_path)


def _write_alert_changes(run_dir: Path, changes: pd.DataFrame) -> Path:
    path = run_dir / ALERT_CHANGES_NAME
    changes.to_parquet(path, index=False)
    return path


def _change_counts(changes: pd.DataFrame) -> dict[str, int]:
    categories = [
        "new",
        "severity_increased",
        "severity_decreased",
        "unchanged",
        "resolved_below_threshold",
    ]
    counts = {category: 0 for category in categories}
    if not changes.empty:
        counts.update(
            {
                str(category): int(count)
                for category, count in changes["change_category"].value_counts().items()
            }
        )
    return counts


def _new_transaction_count(run_dir: Path, eligible_files: Sequence[InboxFile]) -> int:
    normalized_path = run_dir / "normalized_transactions.parquet"
    if not normalized_path.exists():
        return 0
    eligible_paths = {str(item.path) for item in eligible_files}
    frame = pd.read_parquet(normalized_path, columns=["source_file"])
    if "source_file" not in frame.columns:
        return 0
    return int(frame["source_file"].astype(str).isin(eligible_paths).sum())


def _record_for_file(
    inbox_file: InboxFile,
    *,
    run_id: str,
    status: str,
    processed_at: str,
    error_message: str | None,
) -> ProcessedFileRecord:
    return ProcessedFileRecord(
        file_path=str(inbox_file.path),
        file_sha256=inbox_file.file_sha256,
        first_seen_at=inbox_file.first_seen_at,
        processed_at=processed_at,
        run_id=run_id,
        row_count=_count_csv_rows(inbox_file.path),
        status=status,
        error_message=error_message,
    )


def _inbox_payload(item: InboxFile) -> dict[str, object]:
    payload = asdict(item)
    payload["path"] = str(item.path)
    return payload


def _write_monitoring_summary(
    run_dir: Path,
    *,
    run_id: str,
    prior_run_id: str | None,
    eligible_files: Sequence[InboxFile],
    skipped_files: Sequence[InboxFile],
    processed_records: Sequence[ProcessedFileRecord],
    alert_change_counts: dict[str, int],
    new_transaction_count: int,
    processed_state_path: Path,
    monitoring_log_path: Path,
    okf_log_path: Path | None,
) -> Path:
    summary_path = run_dir / MONITORING_SUMMARY_NAME
    payload = {
        "run_id": run_id,
        "prior_run_id": prior_run_id,
        "processed_file_count": len(eligible_files),
        "skipped_file_count": len(skipped_files),
        "failed_file_count": 0,
        "new_transaction_count": new_transaction_count,
        "processed_files": [asdict(record) for record in processed_records],
        "skipped_files": [_inbox_payload(item) for item in skipped_files],
        "alert_change_counts": alert_change_counts,
        "processed_files_state": str(processed_state_path),
        "okf_monitoring_log": str(monitoring_log_path),
        "okf_bundle_log": str(okf_log_path) if okf_log_path is not None else None,
        "human_review_required": True,
    }
    summary_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return summary_path


def _append_monitoring_log(
    path: Path,
    *,
    run_id: str,
    prior_run_id: str | None,
    alert_change_counts: dict[str, int],
    processed_records: Sequence[ProcessedFileRecord],
    skipped_files: Sequence[InboxFile],
    okf_concept_count: int,
    okf_validation_valid: bool,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "run_id": run_id,
        "prior_run_id": prior_run_id,
        "processed_files": [asdict(record) for record in processed_records],
        "skipped_files": [_inbox_payload(item) for item in skipped_files],
        "alert_change_counts": alert_change_counts,
        "okf_concept_count": okf_concept_count,
        "okf_validation_valid": okf_validation_valid,
        "human_review_required": True,
        "created_at": _now(),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True, default=str) + "\n")
    return path


def _append_okf_monitoring_log(
    bundle_path: Path,
    *,
    run_id: str,
    prior_run_id: str | None,
    alert_change_counts: dict[str, int],
) -> Path:
    log_path = bundle_path / "log.md"
    date_text = datetime.now(UTC).date().isoformat()
    lines = [
        "",
        f"## Monitoring update {date_text}",
        "",
        f"- Run `{run_id}` refreshed suspicious indicators requiring human review.",
        f"- Prior run: `{prior_run_id or 'none'}`.",
        f"- Alert changes: `{json.dumps(alert_change_counts, sort_keys=True)}`.",
        "- This monitoring update is an investigative aid, not a confirmed fraud judgment.",
        "",
    ]
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    return log_path


def _failed_result(
    *,
    run_id: str,
    artifacts_dir: Path,
    state_path: Path,
    log_path: Path,
    eligible_files: Sequence[InboxFile],
    skipped_files: Sequence[InboxFile],
    error: Exception,
    stage_timings: dict[str, float],
) -> MonitoringResult:
    processed_at = _now()
    failed_records = [
        _record_for_file(
            item,
            run_id=run_id,
            status=FAILED_STATUS,
            processed_at=processed_at,
            error_message=str(error),
        )
        for item in eligible_files
    ]
    existing = load_processed_state(state_path)
    write_processed_state(state_path, [*existing, *failed_records])
    return MonitoringResult(
        run_id=run_id,
        run_dir=None,
        run_created=False,
        prior_run_id=None,
        processed_file_count=0,
        skipped_file_count=len(skipped_files),
        failed_file_count=len(failed_records),
        new_transaction_count=0,
        alert_change_counts={},
        processed_state_path=state_path,
        monitoring_log_path=log_path,
        monitoring_summary_path=None,
        alert_changes_path=None,
        manifest_path=None,
        okf_log_path=None,
        stage_timings_seconds=stage_timings,
        output_paths={
            "processed_files_state": state_path,
            "monitoring_log": log_path,
            "monitoring_dir": _monitoring_dir(artifacts_dir),
        },
    )


def _run_pipeline(
    input_paths: Sequence[Path],
    *,
    run_id: str,
    artifacts_dir: Path,
    force: bool,
    stage_timings: dict[str, float],
) -> tuple[dict[str, Any], Any, Any]:
    started_at = perf_counter()
    ingestion = ingest_transactions(
        input_paths,
        run_id=run_id,
        artifacts_dir=artifacts_dir,
        force=force,
    )
    report = profile_run(ingestion.run_dir, ingestion.source_data_fingerprint)
    phase2_manifest = build_phase2_manifest(ingestion, report)
    phase2_manifest["pipeline_config_hash"] = canonical_yaml_hash("config/pipeline.yaml")
    stage_timings["monitor_snapshot"] = round(perf_counter() - started_at, 6)

    started_at = perf_counter()
    feature_result = compute_account_features(ingestion.run_dir)
    stage_timings["feature_engineering"] = round(perf_counter() - started_at, 6)

    started_at = perf_counter()
    scoring_result = score_accounts(ingestion.run_dir)
    stage_timings["scoring"] = round(perf_counter() - started_at, 6)

    started_at = perf_counter()
    alert_result = generate_alerts(ingestion.run_dir)
    stage_timings["alert_generation"] = round(perf_counter() - started_at, 6)

    phase3_manifest = build_phase3_manifest(
        phase2_manifest,
        feature_result,
        scoring_result,
        alert_result,
        stage_timings,
    )

    started_at = perf_counter()
    graph_result = build_graph_artifacts(ingestion.run_dir)
    stage_timings["graph_build"] = round(perf_counter() - started_at, 6)

    started_at = perf_counter()
    cluster_result = identify_clusters(ingestion.run_dir)
    stage_timings["clustering"] = round(perf_counter() - started_at, 6)

    manifest = build_phase4_manifest(
        phase3_manifest,
        graph_result,
        cluster_result,
        stage_timings,
    )
    write_run_manifest(ingestion.run_dir, manifest)

    started_at = perf_counter()
    export_result = export_okf_bundle(ingestion.run_dir)
    stage_timings["okf_export"] = round(perf_counter() - started_at, 6)

    started_at = perf_counter()
    validation_result = validate_okf_bundle(
        export_result.bundle_path,
        report_path=ingestion.run_dir / "okf_validation_report.json",
    )
    stage_timings["okf_validate"] = round(perf_counter() - started_at, 6)

    manifest = build_phase5_manifest(
        manifest,
        export_result,
        validation_result,
        stage_timings,
    )
    if not validation_result.valid:
        write_run_manifest(ingestion.run_dir, manifest)
        raise MonitoringError(
            f"OKF validation failed with {len(validation_result.hard_errors)} hard errors"
        )
    return manifest, export_result, validation_result


def process_inbox(
    inbox: Path | str,
    *,
    artifacts_dir: Path | str = "artifacts",
    force: bool = False,
    run_id: str | None = None,
) -> MonitoringResult:
    """Process new inbox files through a deterministic full-snapshot monitor run."""

    artifacts_path = Path(artifacts_dir)
    actual_run_id = run_id or _generated_run_id()
    state_path = _state_path(artifacts_path)
    log_path = _log_path(artifacts_path)
    stage_timings: dict[str, float] = {}

    started_at = perf_counter()
    files = discover_inbox_files(inbox)
    records = load_processed_state(state_path)
    eligible_files, skipped_files = select_eligible_files(files, records, force=force)
    stage_timings["monitor_discovery"] = round(perf_counter() - started_at, 6)

    if not eligible_files:
        return MonitoringResult(
            run_id=None,
            run_dir=None,
            run_created=False,
            prior_run_id=None,
            processed_file_count=0,
            skipped_file_count=len(skipped_files),
            failed_file_count=0,
            new_transaction_count=0,
            alert_change_counts={},
            processed_state_path=state_path,
            monitoring_log_path=log_path,
            monitoring_summary_path=None,
            alert_changes_path=None,
            manifest_path=None,
            okf_log_path=None,
            stage_timings_seconds=stage_timings,
            output_paths={
                "processed_files_state": state_path,
                "monitoring_log": log_path,
                "monitoring_dir": _monitoring_dir(artifacts_path),
            },
        )

    prior_run = _latest_successful_run(artifacts_path, exclude_run_id=actual_run_id)
    prior_snapshot = (
        _write_prior_snapshot(prior_run, artifacts_path, actual_run_id)
        if prior_run is not None
        else None
    )
    input_paths = [*([] if prior_snapshot is None else [prior_snapshot])]
    input_paths.extend(item.path for item in eligible_files)

    try:
        manifest, export_result, validation_result = _run_pipeline(
            input_paths,
            run_id=actual_run_id,
            artifacts_dir=artifacts_path,
            force=force,
            stage_timings=stage_timings,
        )
    except Exception as exc:
        _failed_result(
            run_id=actual_run_id,
            artifacts_dir=artifacts_path,
            state_path=state_path,
            log_path=log_path,
            eligible_files=eligible_files,
            skipped_files=skipped_files,
            error=exc,
            stage_timings=stage_timings,
        )
        raise MonitoringError(str(exc)) from exc

    run_dir = artifacts_path / "runs" / actual_run_id
    started_at = perf_counter()
    changes = compare_alerts(
        _read_alerts(prior_run.run_dir if prior_run is not None else None),
        _read_alerts(run_dir),
        run_id=actual_run_id,
        prior_run_id=prior_run.run_id if prior_run is not None else None,
    )
    alert_changes_path = _write_alert_changes(run_dir, changes)
    alert_change_counts = _change_counts(changes)
    stage_timings["alert_comparison"] = round(perf_counter() - started_at, 6)

    processed_at = _now()
    processed_records = [
        _record_for_file(
            item,
            run_id=actual_run_id,
            status=COMPLETED_STATUS,
            processed_at=processed_at,
            error_message=None,
        )
        for item in eligible_files
    ]
    new_transaction_count = _new_transaction_count(run_dir, eligible_files)

    started_at = perf_counter()
    okf_log_path = _append_okf_monitoring_log(
        export_result.bundle_path,
        run_id=actual_run_id,
        prior_run_id=prior_run.run_id if prior_run is not None else None,
        alert_change_counts=alert_change_counts,
    )
    monitoring_log_path = _append_monitoring_log(
        log_path,
        run_id=actual_run_id,
        prior_run_id=prior_run.run_id if prior_run is not None else None,
        alert_change_counts=alert_change_counts,
        processed_records=processed_records,
        skipped_files=skipped_files,
        okf_concept_count=export_result.concept_count,
        okf_validation_valid=bool(validation_result.valid),
    )
    processed_state_path = write_processed_state(
        state_path,
        [*records, *processed_records],
    )
    monitoring_summary_path = _write_monitoring_summary(
        run_dir,
        run_id=actual_run_id,
        prior_run_id=prior_run.run_id if prior_run is not None else None,
        eligible_files=eligible_files,
        skipped_files=skipped_files,
        processed_records=processed_records,
        alert_change_counts=alert_change_counts,
        new_transaction_count=new_transaction_count,
        processed_state_path=processed_state_path,
        monitoring_log_path=monitoring_log_path,
        okf_log_path=okf_log_path,
    )
    stage_timings["monitoring_state_update"] = round(perf_counter() - started_at, 6)

    result = MonitoringResult(
        run_id=actual_run_id,
        run_dir=run_dir,
        run_created=True,
        prior_run_id=prior_run.run_id if prior_run is not None else None,
        processed_file_count=len(eligible_files),
        skipped_file_count=len(skipped_files),
        failed_file_count=0,
        new_transaction_count=new_transaction_count,
        alert_change_counts=alert_change_counts,
        processed_state_path=processed_state_path,
        monitoring_log_path=monitoring_log_path,
        monitoring_summary_path=monitoring_summary_path,
        alert_changes_path=alert_changes_path,
        manifest_path=run_dir / "run_manifest.json",
        okf_log_path=okf_log_path,
        stage_timings_seconds=stage_timings,
        output_paths={
            "run_manifest": run_dir / "run_manifest.json",
            "processed_files_state": processed_state_path,
            "monitoring_log": monitoring_log_path,
            "monitoring_summary": monitoring_summary_path,
            "alert_changes": alert_changes_path,
            "okf_bundle_log": okf_log_path,
        },
    )
    phase7_manifest = build_phase7_manifest(manifest, result, stage_timings)
    manifest_path = write_run_manifest(run_dir, phase7_manifest)
    return MonitoringResult(
        **{
            **asdict(result),
            "manifest_path": manifest_path,
            "output_paths": {**result.output_paths, "run_manifest": manifest_path},
        }
    )
