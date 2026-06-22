# Phase 8 Performance And Demo Hardening Design

## Summary

Phase 8 hardens the existing deterministic fraud-demo pipeline for reliable
benchmarking and presentation. It adds a repeatable benchmark flow, a small
smoke benchmark path, demo orchestration scripts, fallback artifact guidance,
and updated runbook documentation without changing the rule-based detection
logic.

All benchmark and demo outputs remain suspicious indicators requiring human
review, not confirmed fraud. Phase 8 does not introduce external model or API
calls, does not commit large generated datasets, and keeps the one-million-row
benchmark outside the default unit test suite.

## Requirements

- Follow `PRD.md` Phase 8 and AGENTS.md.
- Preserve deterministic, rule-based detection.
- Do not send raw transaction data to external models or APIs.
- Keep generated large CSV, Parquet, DuckDB, OKF, and dashboard artifacts out of
  Git.
- Provide a benchmark path that can generate or reuse a dataset, run the full
  pipeline, validate row reconciliation, validate OKF output, capture run
  manifest stage timings, capture peak memory where the local platform exposes
  it, and write deterministic `benchmark_report.json`.
- Provide a smaller smoke benchmark path suitable for CI and quick local
  verification.
- Add demo script or Makefile targets for sample data generation, full pipeline
  execution, monitoring delta demonstration, OKF validation, and dashboard
  artifact preparation.
- Document fallback artifact flow without committing large generated data.
- Confirm the dashboard still reads prepared artifacts only and does not load raw
  CSV files on page render.
- Confirm no external model/API calls are introduced.

## Design Options

### Option A: Shell-only benchmark script

Keep `scripts/benchmark.sh` as a pure shell script that runs data generation,
the pipeline, `validate-okf`, and ad hoc JSON checks.

Trade-offs: This has fewer Python files, but row reconciliation and report
format validation would be brittle in shell. It would also be difficult to unit
test report generation and failure behavior.

### Option B: Python benchmark helper with shell orchestration

Add `src/fraud_demo/benchmarking.py` for deterministic report assembly,
reconciliation checks, OKF validation checks, report writing, and CLI-friendly
error handling. Keep `scripts/benchmark.sh` responsible for process orchestration,
timing, optional memory capture, and environment defaults.

Trade-offs: This adds one focused Python module, but makes the benchmark report
testable, stable, and easier for both the Makefile and scripts to reuse.

### Option C: New Typer `benchmark` command

Expose benchmark orchestration directly in the application CLI.

Trade-offs: This would be convenient, but the PRD specifically names
`scripts/benchmark.sh`, and benchmark execution needs shell-level memory tools
such as `/usr/bin/time` when available. A CLI command can be added later if
needed.

## Decision

Use Option B. Phase 8 adds a small benchmark-report helper and keeps
`scripts/benchmark.sh` as the presenter-friendly entrypoint.

The report helper will:

- Load `run_manifest.json`, `ingestion_summary.json`, `okf_validation_report.json`,
  and prepared Parquet artifacts from a run directory.
- Validate row reconciliation:
  `raw_row_count == valid_row_count + rejected_row_count + duplicate_row_count`.
- Validate `sum_valid_amount` against the normalized transaction amount sum.
- Validate every alert references an existing account-risk row.
- Validate every high and critical alert has triggered rule evidence.
- Validate OKF hard errors are zero.
- Write `benchmark_report.json` with stable key ordering and deterministic
  values derived from artifacts and script-provided metadata.

The shell script will:

- Default to the full one-million-row benchmark.
- Support smoke mode through environment variables, with a small row count and
  separate run ID/artifact directory.
- Generate the dataset only when missing or when forced.
- Run the full pipeline with `--force` for the selected benchmark run.
- Capture wall-clock seconds using shell timing.
- Capture peak memory in kilobytes when `/usr/bin/time -l` or `/usr/bin/time -v`
  is available; otherwise record `null` plus an explanatory note.
- Call the Python helper to validate outputs and write the report.

## Benchmark Report Shape

`benchmark_report.json` will include:

- `schema_version`
- `benchmark_mode`
- `row_target`
- `dataset_path`
- `dataset_generated`
- `artifacts_dir`
- `run_id`
- `run_dir`
- `run_manifest_path`
- `generated_at`
- `pipeline_wall_seconds`
- `peak_memory_kb`
- `peak_memory_source`
- `stage_timings_seconds`
- `row_reconciliation`
- `amount_reconciliation`
- `alert_reconciliation`
- `okf_validation`
- `artifact_paths`
- `human_review_required`
- `external_model_api_calls`

Generated timestamps come from run artifacts or current UTC runtime and are not
used for pass/fail comparisons in tests.

## Demo Hardening

Phase 8 updates `scripts/demo_setup.sh` and `scripts/demo_run.sh`, and adds a
monitoring delta script if needed. Makefile targets will wrap these scripts:

- `sample-data`
- `run-sample`
- `demo-prepare`
- `demo-monitor`
- `validate-okf`
- `dashboard`
- `benchmark`
- `benchmark-smoke`

The fallback flow will be documented as commands that regenerate local artifacts
from deterministic seeds instead of committing generated data.

## Dashboard Boundary

The dashboard remains a prepared-artifact consumer. Phase 8 will not add raw CSV
reads to `dashboard/`. Tests and verification will continue to guard against
`pd.read_csv` calls during dashboard artifact loading.

## Error Handling

- Missing benchmark run artifacts are hard failures.
- Row reconciliation failure is a hard failure.
- OKF hard validation errors are hard failures.
- Missing peak-memory tooling is not a failure; the report records `null` memory
  and a source note.
- Missing smoke/full datasets are generated deterministically.

## Testing

Use TDD for behavior changes. Tests cover:

- Successful benchmark report generation from prepared artifacts.
- Benchmark report fields and deterministic write ordering.
- Row reconciliation failure.
- Alert-to-risk reconciliation failure.
- OKF hard-error failure.
- Demo script and Makefile assumptions where practical.
- Dashboard no-raw-CSV loading guard.

The one-million-row benchmark remains manual and documented. The smoke benchmark
is used for quick local verification.

## Out Of Scope

- Rewriting feature engineering or scoring unless the benchmark exposes a
  verified bottleneck that blocks demo targets.
- Adding machine-learning models or runtime LLM narration.
- Committing generated benchmark datasets or large artifacts.
- Building a production scheduler or daemon.
