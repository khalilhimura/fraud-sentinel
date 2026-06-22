#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-.venv/bin/python}
BENCHMARK_MODE=${BENCHMARK_MODE:-full}
BENCHMARK_ROWS=${BENCHMARK_ROWS:-1000000}
BENCHMARK_DATASET=${BENCHMARK_DATASET:-data/raw/transactions_${BENCHMARK_ROWS}.csv}
BENCHMARK_ARTIFACTS_DIR=${BENCHMARK_ARTIFACTS_DIR:-artifacts}
BENCHMARK_RUN_ID=${BENCHMARK_RUN_ID:-RUN_BENCHMARK_${BENCHMARK_MODE}}
BENCHMARK_REPORT=${BENCHMARK_REPORT:-benchmark_report.json}
BENCHMARK_FORCE_DATA=${BENCHMARK_FORCE_DATA:-0}
BENCHMARK_SEED=${BENCHMARK_SEED:-42}

mkdir -p "$(dirname "$BENCHMARK_DATASET")" "$BENCHMARK_ARTIFACTS_DIR" "$(dirname "$BENCHMARK_REPORT")"

DATASET_GENERATED=0
if [[ ! -f "$BENCHMARK_DATASET" || "$BENCHMARK_FORCE_DATA" == "1" ]]; then
  "$PYTHON_BIN" -m fraud_demo generate-data \
    --rows "$BENCHMARK_ROWS" \
    --output "$BENCHMARK_DATASET" \
    --seed "$BENCHMARK_SEED"
  DATASET_GENERATED=1
else
  printf "Using existing benchmark dataset: %s\n" "$BENCHMARK_DATASET"
fi

TIME_LOG=$(mktemp "${TMPDIR:-/tmp}/fraud-sentinel-benchmark-time.XXXXXX")
PIPELINE_START=$("$PYTHON_BIN" -c 'import time; print(time.perf_counter())')
PEAK_MEMORY_KB=null
PEAK_MEMORY_SOURCE=unavailable

if [[ -x /usr/bin/time ]] && /usr/bin/time -l true >/dev/null 2>&1; then
  if ! /usr/bin/time -l "$PYTHON_BIN" -m fraud_demo run \
    --input "$BENCHMARK_DATASET" \
    --run-id "$BENCHMARK_RUN_ID" \
    --artifacts-dir "$BENCHMARK_ARTIFACTS_DIR" \
    --force 2>"$TIME_LOG"; then
    cat "$TIME_LOG" >&2
    exit 1
  fi
  PEAK_BYTES=$(awk '/maximum resident set size/ {print $1}' "$TIME_LOG" | tail -1)
  if [[ "$PEAK_BYTES" =~ ^[0-9]+$ ]]; then
    PEAK_MEMORY_KB=$(( (PEAK_BYTES + 1023) / 1024 ))
    PEAK_MEMORY_SOURCE="/usr/bin/time -l"
  fi
elif [[ -x /usr/bin/time ]] && /usr/bin/time -v true >/dev/null 2>&1; then
  if ! /usr/bin/time -v "$PYTHON_BIN" -m fraud_demo run \
    --input "$BENCHMARK_DATASET" \
    --run-id "$BENCHMARK_RUN_ID" \
    --artifacts-dir "$BENCHMARK_ARTIFACTS_DIR" \
    --force 2>"$TIME_LOG"; then
    cat "$TIME_LOG" >&2
    exit 1
  fi
  PEAK_KB=$(awk -F: '/Maximum resident set size/ {gsub(/ /, "", $2); print $2}' "$TIME_LOG" | tail -1)
  if [[ "$PEAK_KB" =~ ^[0-9]+$ ]]; then
    PEAK_MEMORY_KB=$PEAK_KB
    PEAK_MEMORY_SOURCE="/usr/bin/time -v"
  fi
else
  "$PYTHON_BIN" -m fraud_demo run \
    --input "$BENCHMARK_DATASET" \
    --run-id "$BENCHMARK_RUN_ID" \
    --artifacts-dir "$BENCHMARK_ARTIFACTS_DIR" \
    --force
fi

PIPELINE_END=$("$PYTHON_BIN" -c 'import time; print(time.perf_counter())')
PIPELINE_WALL_SECONDS=$("$PYTHON_BIN" -c "print(round($PIPELINE_END - $PIPELINE_START, 6))")
rm -f "$TIME_LOG"

REPORT_ARGS=(
  --run-dir "$BENCHMARK_ARTIFACTS_DIR/runs/$BENCHMARK_RUN_ID"
  --dataset-path "$BENCHMARK_DATASET"
  --report-path "$BENCHMARK_REPORT"
  --benchmark-mode "$BENCHMARK_MODE"
  --row-target "$BENCHMARK_ROWS"
  --artifacts-dir "$BENCHMARK_ARTIFACTS_DIR"
  --pipeline-wall-seconds "$PIPELINE_WALL_SECONDS"
  --peak-memory-kb "$PEAK_MEMORY_KB"
  --peak-memory-source "$PEAK_MEMORY_SOURCE"
)
if [[ "$DATASET_GENERATED" == "1" ]]; then
  REPORT_ARGS+=(--dataset-generated)
fi

"$PYTHON_BIN" -m fraud_demo.benchmarking "${REPORT_ARGS[@]}"
