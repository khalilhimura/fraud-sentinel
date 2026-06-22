# Phase 7 File-Based Monitoring Design

## Summary

Phase 7 implements deterministic file-based micro-batch monitoring for
`python -m fraud_demo monitor --inbox data/incoming`. The monitor discovers
`transactions_*.csv` files, records processed-file state by SHA-256 hash, builds
a full current analytical snapshot, compares alert state with the prior
successful run, refreshes OKF and dashboard-ready artifacts, and records the
monitoring run provenance.

All outputs remain suspicious indicators requiring human review, not confirmed
fraud. The monitor uses only local files and the existing deterministic
pipeline modules. It does not call external models or APIs.

## Requirements

- Follow `PRD.md` Phase 7, FR-001 through FR-005, FR-022 through FR-025,
  FR-027, FR-029, FR-030, and AGENTS.md.
- Maintain processed-file state with:
  `file_path`, `file_sha256`, `first_seen_at`, `processed_at`, `run_id`,
  `row_count`, `status`, and `error_message`.
- Discover only `transactions_*.csv` files in the provided inbox.
- Skip files whose hash has already completed successfully unless `--force` is
  supplied.
- Keep failed files retryable.
- Deduplicate transaction IDs across files.
- Allow full snapshot recomputation for the MVP.
- Compare current and prior alerts and classify changes as `new`,
  `severity_increased`, `severity_decreased`, `unchanged`, or
  `resolved_below_threshold`.
- Preserve run history and do not delete prior run concepts silently.
- Regenerate/update the OKF bundle deterministically and append/update an OKF
  monitoring log.
- Refresh dashboard-readable artifacts and manifests.
- Preserve run IDs, source fingerprints, file hashes, config hashes, stage
  timings, and artifact paths.

## Design Options

### Option A: Monitoring orchestrator over the existing full pipeline

Create `src/fraud_demo/monitoring.py` as an orchestration layer. It reads and
writes monitoring state, selects eligible inbox files, combines them with the
latest successful snapshot when present, and runs the same ingestion, profile,
feature, scoring, alert, graph, cluster, OKF export, and validation modules used
by the main pipeline.

Trade-offs: This is the safest MVP path because provenance and artifact formats
stay aligned with Phases 2 through 6. It recomputes the full snapshot, which is
acceptable for Phase 7 but not optimal for very large production workloads.

### Option B: Incremental append and affected-account recomputation

Append valid transactions to a canonical table and recompute only accounts
touched by the new files.

Trade-offs: This is faster for large datasets but adds new correctness risk
around affected-account graph neighborhoods, pass-through windows, clusters,
and OKF concept updates. The PRD explicitly allows full recomputation for the
MVP.

### Option C: Dashboard-local monitoring deltas only

Leave the pipeline unchanged and compute alert differences inside dashboard
helpers from two selected runs.

Trade-offs: This would improve display but would not satisfy processed-file
state, retry behavior, run manifests, OKF log updates, or CLI requirements.

## Decision

Use Option A. Phase 7 adds a deterministic monitoring orchestrator that reuses
the existing full-pipeline stages and writes explicit monitoring artifacts:

- `artifacts/monitoring/processed_files.json`
- `artifacts/monitoring/monitoring_log.jsonl`
- `artifacts/runs/<run_id>/monitoring_summary.json`
- `artifacts/runs/<run_id>/alert_changes.parquet`

The canonical latest OKF bundle continues to live at `artifacts/okf_bundle/`.
The monitor also updates the bundle `log.md` with a monitoring entry and keeps
the machine-readable JSONL log outside the bundle for dashboard and audit use.

## Run Selection

The monitor discovers candidates with:

```text
<inbox>/transactions_*.csv
```

Files are sorted by path for deterministic processing. For each file, the
monitor computes SHA-256 and checks `processed_files.json`.

- If the hash has a successful `completed` record and `--force` is not set, the
  file is skipped.
- If a prior record for the hash failed, the file remains eligible.
- If `--force` is set, completed hashes are eligible again, and new state rows
  record the new run ID.

When no files are eligible, the command exits successfully with a clear message
and does not create a new analytical run.

## Snapshot Strategy

The monitor builds a new full snapshot from:

1. The latest successful monitoring or full-pipeline run's
   `normalized_transactions.parquet`, when available.
2. The eligible inbox files for the current micro-batch.

The combined input is written to the new run by calling the existing ingestion
path with multiple CSV files. Cross-file transaction ID deduplication is
provided by `ingest_transactions`, which keeps the first valid transaction ID
and quarantines later duplicates as `duplicate_transaction_id`.

This approach keeps the MVP deterministic and leaves incremental recomputation
for a later phase.

## Alert Comparison

Alert comparison uses stable account identity rather than alert ID because
alert IDs include the run ID. The prior and current alert tables are keyed by
`account_id`.

Severity ordering is:

```text
Low < Medium < High < Critical
```

The output `alert_changes.parquet` includes:

- `run_id`
- `prior_run_id`
- `account_id`
- `change_category`
- `prior_alert_id`
- `current_alert_id`
- `prior_risk_level`
- `current_risk_level`
- `prior_risk_score`
- `current_risk_score`
- `prior_triggered_rule_ids`
- `current_triggered_rule_ids`
- `human_review_note`
- `created_at`

Current alerts with no prior alert are `new`. Current alerts with prior alerts
are compared by severity and score for `severity_increased`,
`severity_decreased`, or `unchanged`. Prior alerts absent from the current alert
table are `resolved_below_threshold`.

## Manifest And Provenance

The Phase 7 manifest extends the Phase 5 manifest with:

- `status = phase7_complete`
- `phase_status.phase7_monitoring = complete`
- `monitoring_run = true`
- `prior_run_id`
- `processed_file_count`
- `skipped_file_count`
- `alert_change_counts`
- `stage_timings_seconds.monitor_discovery`
- `stage_timings_seconds.monitor_snapshot`
- `stage_timings_seconds.alert_comparison`
- `stage_timings_seconds.monitoring_state_update`
- `artifact_paths.processed_files_state`
- `artifact_paths.monitoring_log`
- `artifact_paths.monitoring_summary`
- `artifact_paths.alert_changes`

Existing Phase 2 through Phase 5 provenance remains in the same manifest:
source files, source file fingerprints, source data fingerprint, rules config
hash, pipeline config hash when available, run ID, stage timings, and artifact
paths.

## OKF Monitoring Log

Phase 7 writes two logs:

- `artifacts/monitoring/monitoring_log.jsonl` is the append-only structured
  monitoring log.
- `artifacts/okf_bundle/log.md` is updated with a concise human-readable
  monitoring entry after OKF export.

The log records run ID, prior run ID, processed files, skipped files, alert
change counts, concept count, validation status, and timestamps. It does not
store raw transaction rows.

## Dashboard Impact

The dashboard keeps reading prepared artifacts only. Phase 7 adds helper logic
to prepare monitoring delta data from `alert_changes.parquet`,
`monitoring_summary.json`, and manifest fields. The Monitoring page displays:

- Last successful run and prior run.
- Processed, skipped, and failed files.
- New transactions since the prior run.
- Alert change counts by category.
- Accounts whose severity increased.
- OKF monitoring log path and latest update summary.
- Stage timings and artifact paths.

The dashboard page still does not read raw CSV files on render.

## Error Handling

- Missing inbox directory is a hard failure with a non-zero CLI exit.
- An unreadable or schema-invalid eligible file marks that file as `failed`,
  writes the error message in processed-file state, and returns a non-zero exit
  code.
- A failed file remains retryable on a later monitor run.
- OKF validation failure is a hard failure for the monitoring run.
- The monitor never overwrites a successful run directory unless `--force` is
  supplied.

## Testing

Use TDD for each behavior. Tests cover:

- Processed-file state creation and updates.
- Skipping completed file hashes.
- `--force` reprocessing of completed hashes.
- Failed-file retry behavior.
- Transaction ID deduplication across files.
- Alert comparison categories.
- Monitoring manifest fields and stage timings.
- OKF monitoring log updates.
- CLI `monitor` success and failure paths.
- Monitoring dashboard delta data preparation.

## Out Of Scope

- True streaming or a file watcher daemon.
- Incremental affected-account recomputation.
- External model/API calls.
- Analyst disposition workflow.
- Generating one Markdown file per raw transaction.
