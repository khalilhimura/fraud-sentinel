# Phase 2 Data Pipeline Design

## Scope

Phase 2 implements the PRD slice for synthetic data generation, CSV schema validation, normalization, rejected-row quarantine, and data-quality profiling. It does not implement feature engineering, scoring, graph construction, OKF export, dashboard artifact loading, or monitoring beyond keeping compatible artifact paths.

## Architecture

The pipeline remains file-first and deterministic. `generate_data.py` creates reproducible synthetic transaction CSVs plus a scenario manifest. `ingest.py` validates one or more CSV files, normalizes required and recommended fields, deduplicates valid transactions by `transaction_id`, writes `normalized_transactions.parquet` and `rejected_rows.parquet`, and records source fingerprints. `profile.py` reads the Phase 2 artifacts and writes `data_quality_report.json`.

CLI commands are wired as follows:

- `generate-data` writes synthetic CSV and scenario manifest.
- `profile` validates and profiles a CSV into a generated profile run directory.
- `run` executes Phase 2 ingestion and profiling for the supplied run ID, then writes a Phase 2 run manifest that marks later stages as pending.

## Data Handling

Rows are rejected when required identifiers are blank, timestamps cannot be parsed, amounts are non-positive or invalid, or currencies are missing. Duplicate valid transaction IDs are removed after validation and quarantined with a `duplicate_transaction_id` rejection code. Normalized timestamps are UTC ISO timestamps in Parquet-compatible columns, identifiers are trimmed, blank strings become nulls, currency and country codes are uppercased, and source filename plus source row number are preserved.

## Testing

Phase 2 uses red-green tests for generator reproducibility, ingestion normalization and rejection behavior, profile report fields, and CLI artifact creation. The default verification remains `pytest -q`, `ruff check .`, and focused CLI smoke commands on small generated files.

## Approval

The user approved proceeding with Phase 2 on 2026-06-22 after confirming the PRD phase count.

