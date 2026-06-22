#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-.venv/bin/python}
DEMO_SAMPLE_PATH=${DEMO_SAMPLE_PATH:-data/samples/transactions_sample.csv}
DEMO_ARTIFACTS_DIR=${DEMO_ARTIFACTS_DIR:-artifacts}
DEMO_RUN_ID=${DEMO_RUN_ID:-RUN_SAMPLE}
DEMO_SAMPLE_ROWS=${DEMO_SAMPLE_ROWS:-25000}
DEMO_SEED=${DEMO_SEED:-42}

mkdir -p "$(dirname "$DEMO_SAMPLE_PATH")" "$DEMO_ARTIFACTS_DIR"

if [[ ! -f "$DEMO_SAMPLE_PATH" ]]; then
  "$PYTHON_BIN" -m fraud_demo generate-data \
    --rows "$DEMO_SAMPLE_ROWS" \
    --output "$DEMO_SAMPLE_PATH" \
    --seed "$DEMO_SEED"
fi

"$PYTHON_BIN" -m fraud_demo run \
  --input "$DEMO_SAMPLE_PATH" \
  --run-id "$DEMO_RUN_ID" \
  --artifacts-dir "$DEMO_ARTIFACTS_DIR" \
  --force
"$PYTHON_BIN" -m fraud_demo validate-okf --bundle artifacts/okf_bundle

printf "Demo run complete.\n"
printf "  Run ID: %s\n" "$DEMO_RUN_ID"
printf "  Run manifest: %s/runs/%s/run_manifest.json\n" "$DEMO_ARTIFACTS_DIR" "$DEMO_RUN_ID"
printf "  OKF bundle: artifacts/okf_bundle\n"
printf "  Dashboard: make dashboard\n"
