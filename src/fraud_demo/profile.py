"""Data-quality profiling for Phase 2 artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def _json_safe(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def profile_run(run_dir: Path | str, source_data_fingerprint: str) -> dict[str, object]:
    """Profile normalized and rejected transaction artifacts for a run."""

    run_path = Path(run_dir)
    normalized_path = run_path / "normalized_transactions.parquet"
    rejected_path = run_path / "rejected_rows.parquet"

    normalized = pd.read_parquet(normalized_path)
    rejected = pd.read_parquet(rejected_path)

    accounts = pd.concat(
        [
            normalized.get("sender_account_id", pd.Series(dtype="string")),
            normalized.get("receiver_account_id", pd.Series(dtype="string")),
        ],
        ignore_index=True,
    ).dropna()

    report: dict[str, object] = {
        "run_id": run_path.name,
        "source_data_fingerprint": source_data_fingerprint,
        "valid_row_count": int(len(normalized)),
        "rejected_row_count": int(len(rejected)),
        "distinct_account_count": int(accounts.nunique()),
        "total_amount": round(float(normalized["amount"].sum()), 2)
        if "amount" in normalized
        else 0.0,
        "currency_counts": {
            str(key): int(value)
            for key, value in normalized.get("currency", pd.Series(dtype="string"))
            .value_counts()
            .sort_index()
            .to_dict()
            .items()
        },
        "rejection_counts": {
            str(key): int(value)
            for key, value in rejected.get("rejection_code", pd.Series(dtype="string"))
            .value_counts()
            .sort_index()
            .to_dict()
            .items()
        },
        "event_timestamp_min": _json_safe(normalized["event_timestamp"].min())
        if "event_timestamp" in normalized and not normalized.empty
        else None,
        "event_timestamp_max": _json_safe(normalized["event_timestamp"].max())
        if "event_timestamp" in normalized and not normalized.empty
        else None,
    }

    report_path = run_path / "data_quality_report.json"
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
