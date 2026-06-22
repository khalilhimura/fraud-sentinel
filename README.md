# Fraud Sentinel

Local, deterministic fraud-analysis demo for detecting suspicious mule-account patterns from banking transaction CSV files and exporting investigation knowledge as an OKF v0.1 bundle.

The implementation follows `PRD.md`. Phases 1 through 3 initialize the project scaffold, generate synthetic data, ingest and profile CSV inputs, compute account features, score configurable rules, and write account risk, rule evidence, and alert artifacts. Later phases add graph construction, OKF export, dashboard pages, monitoring, and performance hardening.

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

## Current Commands

```bash
python -m fraud_demo --help
pytest -q
python -m fraud_demo generate-data --rows 120 --output /tmp/fraud-sentinel-sample.csv --seed 42
python -m fraud_demo run --input /tmp/fraud-sentinel-sample.csv --run-id RUN_SAMPLE --force
```

The `validate-okf` and `monitor` commands are present as later-phase skeletons and return clear phase-boundary messages until implemented.

## Project Layout

- `config/`: Rules, pipeline, OKF, and dashboard configuration.
- `src/fraud_demo/`: Python package.
- `dashboard/`: Streamlit application shell.
- `tests/`: Smoke tests and future unit/integration tests.
- `artifacts/`: Generated run outputs and OKF bundles, ignored by Git.
- `data/`: Raw, incoming, and sample data directories, ignored except for `.gitkeep` files.
