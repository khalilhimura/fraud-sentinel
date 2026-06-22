PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip

.PHONY: setup lint test demo-data sample-data run-sample run-demo demo-prepare demo-monitor validate-okf dashboard benchmark benchmark-smoke clean-generated

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -e ".[dev,dashboard]"

lint:
	$(VENV_PYTHON) -m ruff check .

test:
	$(VENV_PYTHON) -m pytest -q

demo-data:
	$(VENV_PYTHON) -m fraud_demo generate-data --rows 1000000 --output data/raw/transactions_1m.csv --seed 42

sample-data:
	$(VENV_PYTHON) -m fraud_demo generate-data --rows 25000 --output data/samples/transactions_sample.csv --seed 42

run-sample:
	$(VENV_PYTHON) -m fraud_demo run --input data/samples/transactions_sample.csv --run-id RUN_SAMPLE --force

run-demo:
	$(VENV_PYTHON) -m fraud_demo run --input data/raw/transactions_1m.csv --run-id RUN_DEMO --force

demo-prepare:
	PYTHON_BIN=$(VENV_PYTHON) scripts/demo_setup.sh

demo-monitor:
	PYTHON_BIN=$(VENV_PYTHON) scripts/demo_monitor_delta.sh

validate-okf:
	$(VENV_PYTHON) -m fraud_demo validate-okf --bundle artifacts/okf_bundle

dashboard:
	$(VENV_PYTHON) -m streamlit run dashboard/app.py

benchmark:
	PYTHON_BIN=$(VENV_PYTHON) scripts/benchmark.sh

benchmark-smoke:
	BENCHMARK_MODE=smoke BENCHMARK_ROWS=1000 BENCHMARK_DATASET=/private/tmp/fraud-sentinel-benchmark-smoke.csv BENCHMARK_ARTIFACTS_DIR=/private/tmp/fraud-sentinel-benchmark-smoke-artifacts BENCHMARK_RUN_ID=RUN_BENCHMARK_SMOKE BENCHMARK_REPORT=/private/tmp/fraud-sentinel-benchmark-smoke-report.json PYTHON_BIN=$(VENV_PYTHON) scripts/benchmark.sh

clean-generated:
	@printf "Refusing to clean generated outputs automatically. Remove data and artifacts manually after review.\n"
