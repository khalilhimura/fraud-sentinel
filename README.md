# Fraud Sentinel

Local, deterministic fraud-analysis demo for detecting suspicious mule-account patterns from banking transaction CSV files and exporting investigation knowledge as an OKF v0.1 bundle.

The implementation follows `PRD.md`. Phase 1 initializes the project scaffold, configuration, CLI command surface, logging, and smoke tests. Later phases add synthetic data generation, ingestion, scoring, graph construction, OKF export, dashboard pages, monitoring, and performance hardening.

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

## Phase 1 Commands

```bash
python -m fraud_demo --help
pytest -q
```

Commands for later phases are present as CLI skeletons and return clear phase-boundary messages until implemented.

## Project Layout

- `config/`: Rules, pipeline, OKF, and dashboard configuration.
- `src/fraud_demo/`: Python package.
- `dashboard/`: Streamlit application shell.
- `tests/`: Smoke tests and future unit/integration tests.
- `artifacts/`: Generated run outputs and OKF bundles, ignored by Git.
- `data/`: Raw, incoming, and sample data directories, ignored except for `.gitkeep` files.

