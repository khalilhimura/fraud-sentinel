#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-.venv/bin/python}
DEMO_INBOX=${DEMO_INBOX:-data/incoming}
DEMO_DELTA_PATH=${DEMO_DELTA_PATH:-data/incoming/transactions_demo_delta.csv}
DEMO_DELTA_ROWS=${DEMO_DELTA_ROWS:-250}
DEMO_DELTA_SEED=${DEMO_DELTA_SEED:-43}
DEMO_ARTIFACTS_DIR=${DEMO_ARTIFACTS_DIR:-artifacts}
DEMO_MONITOR_RUN_ID=${DEMO_MONITOR_RUN_ID:-RUN_MONITOR_DEMO}

mkdir -p "$DEMO_INBOX" "$DEMO_ARTIFACTS_DIR" "$(dirname "$DEMO_DELTA_PATH")"

"$PYTHON_BIN" -m fraud_demo generate-data \
  --rows "$DEMO_DELTA_ROWS" \
  --output "$DEMO_DELTA_PATH" \
  --seed "$DEMO_DELTA_SEED"

DEMO_DELTA_PATH="$DEMO_DELTA_PATH" "$PYTHON_BIN" - <<'PY'
import os
import pandas as pd

path = os.environ["DEMO_DELTA_PATH"]
frame = pd.read_csv(path, dtype=str, keep_default_na=False)
frame["transaction_id"] = "DELTA_" + frame["transaction_id"].astype(str)
frame.to_csv(path, index=False, lineterminator="\n")
PY

"$PYTHON_BIN" -m fraud_demo monitor \
  --inbox "$DEMO_INBOX" \
  --artifacts-dir "$DEMO_ARTIFACTS_DIR" \
  --run-id "$DEMO_MONITOR_RUN_ID" \
  --force
"$PYTHON_BIN" -m fraud_demo validate-okf --bundle artifacts/okf_bundle

printf "Monitoring delta demo complete.\n"
printf "  Delta file: %s\n" "$DEMO_DELTA_PATH"
printf "  Run manifest: %s/runs/%s/run_manifest.json\n" "$DEMO_ARTIFACTS_DIR" "$DEMO_MONITOR_RUN_ID"
printf "  Monitoring summary: %s/runs/%s/monitoring_summary.json\n" "$DEMO_ARTIFACTS_DIR" "$DEMO_MONITOR_RUN_ID"
