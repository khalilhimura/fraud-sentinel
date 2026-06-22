# Fraud Sentinel

Local, deterministic fraud-analysis demo for detecting suspicious mule-account patterns from banking transaction CSV files and exporting investigation knowledge as an OKF v0.1 bundle.

The implementation follows `PRD.md`. Phases 1 through 8 scaffold the project, generate synthetic data, ingest and profile CSV inputs, compute account features, score configurable rules, write alerts and evidence, build bounded graph artifacts, export and validate an OKF bundle, serve a prepared-artifact dashboard, run file-based monitoring, and provide benchmark/demo hardening.

## Safety Boundary

This system identifies suspicious indicators for human review. It does not confirm fraud, make account decisions, or require a runtime LLM. Use synthetic or approved anonymized data only.

## Setup

```bash
make setup
```

Activate the local environment:

```bash
source .venv/bin/activate
```

## Core Commands

```bash
python -m fraud_demo --help
pytest -q
python -m fraud_demo generate-data --rows 120 --output /tmp/fraud-sentinel-sample.csv --seed 42
python -m fraud_demo run --input /tmp/fraud-sentinel-sample.csv --run-id RUN_SAMPLE --force
python -m fraud_demo validate-okf --bundle artifacts/okf_bundle
python -m fraud_demo monitor --inbox data/incoming
```

## Demo Runbook

Prepare deterministic sample data and fallback artifacts:

```bash
make demo-prepare
```

Run or rerun the sample pipeline:

```bash
make run-sample
scripts/demo_run.sh
```

Run a monitoring delta demonstration:

```bash
make demo-monitor
```

Validate the OKF bundle and start the dashboard:

```bash
make validate-okf
make dashboard
```

The Streamlit dashboard reads prepared Parquet, JSON, and OKF Markdown artifacts. It does not load raw CSV files on normal page render.

## Benchmarking

Run a quick smoke benchmark outside the default pytest suite:

```bash
make benchmark-smoke
```

The smoke report is written to:

```text
/private/tmp/fraud-sentinel-benchmark-smoke-report.json
```

Run the full one-million-row benchmark manually when demo hardware and time allow:

```bash
make benchmark
```

The default full benchmark generates or reuses `data/raw/transactions_1000000.csv`, runs the full pipeline, validates row reconciliation and OKF output, captures peak memory when the local platform exposes it, and writes `benchmark_report.json`.

## Fallback artifact flow

Generated datasets and analytical outputs are intentionally ignored by Git. To recreate fallback artifacts on a demo machine:

```bash
make demo-prepare
make benchmark-smoke
make validate-okf
```

For the full fallback path, run:

```bash
make demo-data
make run-demo
make validate-okf
```

Keep generated CSV, Parquet, DuckDB, OKF, and benchmark output files local unless a small fixture is intentionally reviewed and added.

## Project Layout

- `config/`: Rules, pipeline, OKF, and dashboard configuration.
- `src/fraud_demo/`: Python package.
- `dashboard/`: Streamlit application shell.
- `tests/`: Smoke tests and future unit/integration tests.
- `artifacts/`: Generated run outputs and OKF bundles, ignored by Git.
- `data/`: Raw, incoming, and sample data directories, ignored except for `.gitkeep` files.
