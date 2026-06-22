#!/usr/bin/env bash
set -euo pipefail

python -m fraud_demo generate-data --rows 1000000 --output data/raw/transactions_1m.csv --seed 42
python -m fraud_demo run --input data/raw/transactions_1m.csv --run-id RUN_BENCHMARK
