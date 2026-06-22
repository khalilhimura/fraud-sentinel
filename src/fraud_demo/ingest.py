"""CSV ingestion, validation, normalization, and rejected-row quarantine."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pandas as pd

from fraud_demo.config import file_sha256

REQUIRED_COLUMNS = [
    "transaction_id",
    "event_timestamp",
    "sender_account_id",
    "receiver_account_id",
    "amount",
    "currency",
]

REQUIRED_VALUE_COLUMNS = [
    "transaction_id",
    "sender_account_id",
    "receiver_account_id",
    "currency",
]

CATEGORICAL_UPPERCASE_COLUMNS = [
    "currency",
    "sender_country",
    "receiver_country",
]

REJECTED_COLUMNS = [
    "source_file",
    "source_row_number",
    "rejection_code",
    "rejection_message",
    "raw_values_json",
]


class SchemaValidationError(ValueError):
    """Raised when an input CSV does not satisfy the required schema."""


@dataclass(frozen=True)
class IngestionResult:
    """Artifacts and reconciliation counts from ingestion."""

    run_id: str
    run_dir: Path
    normalized_path: Path
    rejected_path: Path
    valid_row_count: int
    rejected_row_count: int
    duplicate_row_count: int
    raw_row_count: int
    source_files: list[str]
    source_file_fingerprints: dict[str, str]
    source_data_fingerprint: str


def _read_source(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise SchemaValidationError(
            f"{path} is missing required columns: {', '.join(sorted(missing))}"
        )
    frame["source_file"] = str(path)
    frame["source_row_number"] = range(2, len(frame) + 2)
    return frame


def _trim_blank_to_na(series: pd.Series) -> pd.Series:
    trimmed = series.astype("string").str.strip()
    return trimmed.mask(trimmed == "")


def _rejection(raw_row: pd.Series, code: str, message: str) -> dict[str, object]:
    raw_values = {
        str(key): (None if pd.isna(value) else value)
        for key, value in raw_row.drop(labels=["source_file", "source_row_number"], errors="ignore")
        .to_dict()
        .items()
    }
    return {
        "source_file": str(raw_row["source_file"]),
        "source_row_number": int(raw_row["source_row_number"]),
        "rejection_code": code,
        "rejection_message": message,
        "raw_values_json": json.dumps(raw_values, sort_keys=True, default=str),
    }


def _source_data_fingerprint(fingerprints: dict[str, str]) -> str:
    digest = sha256()
    for source_file, fingerprint in sorted(fingerprints.items()):
        digest.update(source_file.encode("utf-8"))
        digest.update(b"\0")
        digest.update(fingerprint.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _prepare_run_dir(run_dir: Path, force: bool) -> None:
    if run_dir.exists() and not force and any(run_dir.iterdir()):
        raise FileExistsError(f"Run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    if force:
        for artifact_name in [
            "normalized_transactions.parquet",
            "rejected_rows.parquet",
            "data_quality_report.json",
            "run_manifest.json",
            "ingestion_summary.json",
        ]:
            artifact_path = run_dir / artifact_name
            if artifact_path.exists():
                artifact_path.unlink()


def ingest_transactions(
    input_paths: Sequence[Path | str],
    run_id: str,
    artifacts_dir: Path | str = "artifacts",
    force: bool = False,
) -> IngestionResult:
    """Validate and normalize transaction CSV files into Phase 2 artifacts."""

    paths = [Path(path) for path in input_paths]
    if not paths:
        raise ValueError("At least one input CSV is required")

    run_dir = Path(artifacts_dir) / "runs" / run_id
    _prepare_run_dir(run_dir, force=force)

    source_file_fingerprints = {str(path): file_sha256(path) for path in paths}
    raw_frames = [_read_source(path) for path in paths]
    raw = pd.concat(raw_frames, ignore_index=True)

    normalized = raw.copy()
    for column in normalized.columns:
        if column != "source_row_number":
            normalized[column] = _trim_blank_to_na(normalized[column])

    normalized["event_timestamp"] = pd.to_datetime(
        normalized["event_timestamp"],
        errors="coerce",
        utc=True,
    )
    normalized["amount"] = pd.to_numeric(normalized["amount"], errors="coerce")
    for column in CATEGORICAL_UPPERCASE_COLUMNS:
        if column in normalized.columns:
            normalized[column] = normalized[column].astype("string").str.upper()

    rejection_rows: list[dict[str, object]] = []
    invalid_mask = pd.Series(False, index=normalized.index)
    for index, row in normalized.iterrows():
        code = ""
        message = ""
        if any(pd.isna(row[column]) for column in REQUIRED_VALUE_COLUMNS):
            code = "missing_required_value"
            message = "One or more required identifier or currency fields are blank."
        elif pd.isna(row["event_timestamp"]):
            code = "invalid_timestamp"
            message = "event_timestamp could not be parsed."
        elif pd.isna(row["amount"]) or float(row["amount"]) <= 0:
            code = "invalid_amount"
            message = "amount must be a positive number."

        if code:
            invalid_mask.loc[index] = True
            rejection_rows.append(_rejection(raw.loc[index], code, message))

    candidate_valid = normalized.loc[~invalid_mask].copy()
    duplicate_mask = candidate_valid.duplicated(subset=["transaction_id"], keep="first")
    duplicate_rows = candidate_valid.loc[duplicate_mask]
    for index, row in duplicate_rows.iterrows():
        rejection_rows.append(
            _rejection(
                raw.loc[index],
                "duplicate_transaction_id",
                f"Duplicate transaction_id {row['transaction_id']} removed; first valid row kept.",
            )
        )

    valid = candidate_valid.loc[~duplicate_mask].copy()
    valid = valid.reset_index(drop=True)

    normalized_path = run_dir / "normalized_transactions.parquet"
    rejected_path = run_dir / "rejected_rows.parquet"
    valid.to_parquet(normalized_path, index=False)
    pd.DataFrame(rejection_rows, columns=REJECTED_COLUMNS).to_parquet(rejected_path, index=False)

    result = IngestionResult(
        run_id=run_id,
        run_dir=run_dir,
        normalized_path=normalized_path,
        rejected_path=rejected_path,
        valid_row_count=int(len(valid)),
        rejected_row_count=int(invalid_mask.sum()),
        duplicate_row_count=int(duplicate_mask.sum()),
        raw_row_count=int(len(raw)),
        source_files=[str(path) for path in paths],
        source_file_fingerprints=source_file_fingerprints,
        source_data_fingerprint=_source_data_fingerprint(source_file_fingerprints),
    )

    summary = {
        "run_id": run_id,
        "raw_row_count": result.raw_row_count,
        "valid_row_count": result.valid_row_count,
        "rejected_row_count": result.rejected_row_count,
        "duplicate_row_count": result.duplicate_row_count,
        "source_files": result.source_files,
        "source_file_fingerprints": result.source_file_fingerprints,
        "source_data_fingerprint": result.source_data_fingerprint,
    }
    (run_dir / "ingestion_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result
