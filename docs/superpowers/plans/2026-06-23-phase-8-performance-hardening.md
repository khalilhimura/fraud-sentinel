# Phase 8 Performance And Demo Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add repeatable benchmark reporting, smoke benchmark verification, demo hardening scripts, and Phase 8 documentation without changing deterministic detection behavior.

**Architecture:** Add a focused Python benchmark helper for artifact validation and deterministic JSON report writing. Keep shell scripts and Makefile targets as orchestration wrappers for dataset generation, pipeline execution, monitoring demo, OKF validation, and dashboard preparation.

**Tech Stack:** Python 3.12+, pandas, Typer CLI modules, shell scripts, Makefile, pytest, Ruff.

## Global Constraints

- Treat `PRD.md` as the source of truth.
- Follow AGENTS.md Phase 8 rules.
- Implement phases in PRD order.
- Keep fraud detection deterministic and rule-based.
- Do not send raw transaction data to external models or APIs.
- Use synthetic or approved anonymized data only.
- Label outputs as suspicious indicators requiring human review, not confirmed fraud.
- Preserve run provenance, configuration hashes, source fingerprints, stage timings, and artifact paths.
- Do not generate one Markdown file per raw transaction.
- Keep dashboard graph rendering bounded by configuration.
- Never weaken or delete valid tests just to make the suite pass.
- Keep the one-million-row benchmark outside the default unit test suite.
- Do not commit large generated data or artifacts.

---

## File Structure

- Create `src/fraud_demo/benchmarking.py`: benchmark report dataclasses/helpers, reconciliation validation, OKF validation checks, deterministic JSON writing, and a small CLI entrypoint for scripts.
- Create `tests/test_benchmarking.py`: TDD coverage for report fields, deterministic writes, row reconciliation failures, alert reconciliation failures, and OKF validation failure behavior.
- Modify `scripts/benchmark.sh`: generate or reuse benchmark dataset, run full pipeline, capture timing and peak memory when available, call the Python helper, and write `benchmark_report.json`.
- Modify `scripts/demo_setup.sh`: prepare deterministic sample/demo inputs and smoke fallback artifacts.
- Modify `scripts/demo_run.sh`: run the sample pipeline, validate OKF, and print dashboard artifact paths.
- Create `scripts/demo_monitor_delta.sh`: generate a deterministic incoming delta, run monitoring, and validate the resulting OKF bundle.
- Modify `Makefile`: add `benchmark-smoke`, `demo-prepare`, `demo-monitor`, and script-backed demo targets.
- Modify `README.md`: document setup, demo runbook, benchmark modes, fallback artifact regeneration, safety boundaries, and large-artifact policy.
- Modify `IMPLEMENTATION_STATUS.md`: record Phase 8 scope, assumptions, verification output, and known limitations.

## Task 1: Benchmark Report Helper

**Files:**
- Create: `tests/test_benchmarking.py`
- Create: `src/fraud_demo/benchmarking.py`

**Interfaces:**
- Produces: `BenchmarkReportError(RuntimeError)`
- Produces: `build_benchmark_report(run_dir: Path | str, dataset_path: Path | str, report_path: Path | str, *, benchmark_mode: str, row_target: int, dataset_generated: bool, artifacts_dir: Path | str, pipeline_wall_seconds: float | None = None, peak_memory_kb: int | None = None, peak_memory_source: str | None = None) -> dict[str, object]`
- Produces: `write_benchmark_report(report: Mapping[str, object], report_path: Path | str) -> Path`

- [ ] **Step 1: Write failing report-success test**

Add a `tests/test_benchmarking.py` fixture that writes a minimal run directory with:

```python
run_manifest = {
    "run_id": "RUN_BENCH",
    "status": "phase5_complete",
    "raw_row_count": 3,
    "valid_row_count": 2,
    "rejected_row_count": 1,
    "duplicate_row_count": 0,
    "source_data_fingerprint": "f" * 64,
    "rules_config_hash": "r" * 64,
    "pipeline_config_hash": "p" * 64,
    "stage_timings_seconds": {"feature_engineering": 0.1, "okf_validate": 0.2},
    "artifact_paths": {"okf_bundle": "artifacts/okf_bundle"},
}
```

Write `normalized_transactions.parquet`, `account_risk.parquet`, `alerts.parquet`,
`rule_evidence.parquet`, `ingestion_summary.json`, and
`okf_validation_report.json`. Assert:

```python
report = build_benchmark_report(
    run_dir,
    dataset_path=tmp_path / "transactions.csv",
    report_path=tmp_path / "benchmark_report.json",
    benchmark_mode="smoke",
    row_target=3,
    dataset_generated=True,
    artifacts_dir=tmp_path / "artifacts",
    pipeline_wall_seconds=1.23,
    peak_memory_kb=123456,
    peak_memory_source="test",
)
assert report["schema_version"] == "1.0"
assert report["run_id"] == "RUN_BENCH"
assert report["row_reconciliation"]["passed"] is True
assert report["amount_reconciliation"]["passed"] is True
assert report["alert_reconciliation"]["passed"] is True
assert report["okf_validation"]["passed"] is True
assert report["human_review_required"] is True
assert report["external_model_api_calls"] == "none"
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/test_benchmarking.py::test_build_benchmark_report_records_required_fields -q`

Expected: FAIL because `fraud_demo.benchmarking` does not exist.

- [ ] **Step 3: Implement minimal helper**

Implement JSON loading, Parquet loading, row reconciliation, amount
reconciliation, alert/risk/evidence checks, OKF hard-error check, report dict
assembly, and deterministic JSON writing with `indent=2` and `sort_keys=True`.

- [ ] **Step 4: Verify Task 1**

Run: `.venv/bin/pytest tests/test_benchmarking.py::test_build_benchmark_report_records_required_fields -q`

Expected: PASS.

## Task 2: Benchmark Failure Behavior

**Files:**
- Modify: `tests/test_benchmarking.py`
- Modify: `src/fraud_demo/benchmarking.py`

**Interfaces:**
- Consumes: `BenchmarkReportError`
- Consumes: `build_benchmark_report`

- [ ] **Step 1: Write failing failure tests**

Add tests that reuse `_write_benchmark_run(tmp_path)` from Task 1:

```python
def test_build_benchmark_report_fails_row_reconciliation(tmp_path):
    run_dir = _write_benchmark_run(tmp_path)
    manifest_path = run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["raw_row_count"] = 99
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    with pytest.raises(BenchmarkReportError, match="row reconciliation"):
        build_benchmark_report(
            run_dir,
            dataset_path=tmp_path / "transactions.csv",
            report_path=tmp_path / "benchmark_report.json",
            benchmark_mode="smoke",
            row_target=3,
            dataset_generated=False,
            artifacts_dir=tmp_path / "artifacts",
        )
```

```python
def test_build_benchmark_report_fails_alert_without_risk_row(tmp_path):
    run_dir = _write_benchmark_run(tmp_path)
    alerts = pd.read_parquet(run_dir / "alerts.parquet")
    alerts.loc[0, "account_id"] = "ACC_MISSING"
    alerts.to_parquet(run_dir / "alerts.parquet", index=False)

    with pytest.raises(BenchmarkReportError, match="alert references"):
        build_benchmark_report(
            run_dir,
            dataset_path=tmp_path / "transactions.csv",
            report_path=tmp_path / "benchmark_report.json",
            benchmark_mode="smoke",
            row_target=3,
            dataset_generated=False,
            artifacts_dir=tmp_path / "artifacts",
        )
```

```python
def test_build_benchmark_report_fails_okf_hard_errors(tmp_path):
    run_dir = _write_benchmark_run(tmp_path)
    report_path = run_dir / "okf_validation_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["valid"] = False
    report["hard_errors"] = [{"code": "missing_type", "path": "accounts/A.md"}]
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    with pytest.raises(BenchmarkReportError, match="OKF validation"):
        build_benchmark_report(
            run_dir,
            dataset_path=tmp_path / "transactions.csv",
            report_path=tmp_path / "benchmark_report.json",
            benchmark_mode="smoke",
            row_target=3,
            dataset_generated=False,
            artifacts_dir=tmp_path / "artifacts",
        )
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/test_benchmarking.py -q`

Expected: FAIL until hard-failure paths raise `BenchmarkReportError`.

- [ ] **Step 3: Implement hard-failure paths**

Raise `BenchmarkReportError` after assembling the failed section so callers get
clear messages. Keep successful reports deterministic.

- [ ] **Step 4: Verify Task 2**

Run: `.venv/bin/pytest tests/test_benchmarking.py -q`

Expected: PASS.

## Task 3: Benchmark Script And Make Targets

**Files:**
- Modify: `scripts/benchmark.sh`
- Modify: `Makefile`
- Modify: `tests/test_benchmarking.py`

**Interfaces:**
- Consumes: `.venv/bin/python -m fraud_demo generate-data`
- Consumes: `.venv/bin/python -m fraud_demo run`
- Consumes: `.venv/bin/python -m fraud_demo.benchmarking`
- Produces: `benchmark_report.json`
- Produces: Make targets `benchmark` and `benchmark-smoke`

- [ ] **Step 1: Write failing script-assumption test**

Add a test that reads `scripts/benchmark.sh` and `Makefile` and asserts:

```python
assert "BENCHMARK_ROWS" in script
assert "BENCHMARK_REPORT" in script
assert "fraud_demo.benchmarking" in script
assert "benchmark-smoke:" in makefile
assert "BENCHMARK_ROWS=1000" in makefile
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/test_benchmarking.py::test_benchmark_script_and_makefile_expose_smoke_mode -q`

Expected: FAIL until script and Makefile are updated.

- [ ] **Step 3: Implement script and Makefile targets**

Update `scripts/benchmark.sh` to support:

```bash
PYTHON_BIN=${PYTHON_BIN:-.venv/bin/python}
BENCHMARK_MODE=${BENCHMARK_MODE:-full}
BENCHMARK_ROWS=${BENCHMARK_ROWS:-1000000}
BENCHMARK_DATASET=${BENCHMARK_DATASET:-data/raw/transactions_${BENCHMARK_ROWS}.csv}
BENCHMARK_ARTIFACTS_DIR=${BENCHMARK_ARTIFACTS_DIR:-artifacts}
BENCHMARK_RUN_ID=${BENCHMARK_RUN_ID:-RUN_BENCHMARK_${BENCHMARK_MODE}}
BENCHMARK_REPORT=${BENCHMARK_REPORT:-benchmark_report.json}
BENCHMARK_FORCE_DATA=${BENCHMARK_FORCE_DATA:-0}
```

Run generation when the dataset is missing or `BENCHMARK_FORCE_DATA=1`, run the
pipeline with `--force`, capture wall-clock seconds, capture peak memory when a
supported `/usr/bin/time` mode is available, and call:

```bash
"$PYTHON_BIN" -m fraud_demo.benchmarking \
  --run-dir "$BENCHMARK_ARTIFACTS_DIR/runs/$BENCHMARK_RUN_ID" \
  --dataset-path "$BENCHMARK_DATASET" \
  --report-path "$BENCHMARK_REPORT" \
  --benchmark-mode "$BENCHMARK_MODE" \
  --row-target "$BENCHMARK_ROWS" \
  --artifacts-dir "$BENCHMARK_ARTIFACTS_DIR" \
  --pipeline-wall-seconds "$PIPELINE_WALL_SECONDS" \
  --peak-memory-kb "$PEAK_MEMORY_KB" \
  --peak-memory-source "$PEAK_MEMORY_SOURCE" \
  $DATASET_GENERATED_FLAG
```

Add Makefile `benchmark-smoke` as:

```makefile
benchmark-smoke:
	BENCHMARK_MODE=smoke BENCHMARK_ROWS=1000 BENCHMARK_DATASET=/private/tmp/fraud-sentinel-benchmark-smoke.csv BENCHMARK_ARTIFACTS_DIR=/private/tmp/fraud-sentinel-benchmark-smoke-artifacts BENCHMARK_RUN_ID=RUN_BENCHMARK_SMOKE BENCHMARK_REPORT=/private/tmp/fraud-sentinel-benchmark-smoke-report.json scripts/benchmark.sh
```

- [ ] **Step 4: Verify Task 3**

Run: `.venv/bin/pytest tests/test_benchmarking.py::test_benchmark_script_and_makefile_expose_smoke_mode -q`

Expected: PASS.

## Task 4: Demo Hardening Scripts And Docs

**Files:**
- Modify: `scripts/demo_setup.sh`
- Modify: `scripts/demo_run.sh`
- Create: `scripts/demo_monitor_delta.sh`
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `tests/test_benchmarking.py`

**Interfaces:**
- Produces: `make demo-prepare`
- Produces: `make demo-monitor`
- Produces: deterministic sample and delta paths under `data/samples/` and `data/incoming/`

- [ ] **Step 1: Write failing demo-script assumption test**

Add a test that asserts:

```python
assert Path("scripts/demo_monitor_delta.sh").exists()
assert "RUN_SAMPLE" in Path("scripts/demo_run.sh").read_text()
assert "validate-okf" in Path("scripts/demo_run.sh").read_text()
assert "demo-prepare:" in Path("Makefile").read_text()
assert "demo-monitor:" in Path("Makefile").read_text()
assert "Fallback artifact flow" in Path("README.md").read_text()
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/test_benchmarking.py::test_demo_scripts_makefile_and_readme_document_operating_flow -q`

Expected: FAIL until scripts/docs are updated.

- [ ] **Step 3: Implement demo scripts and docs**

Update scripts to use `.venv/bin/python` by default, deterministic seeds, `--force`
for repeatable demo runs, local artifact paths, OKF validation, and monitoring
delta generation. Update README with setup, quick demo, monitoring demo, smoke
benchmark, full benchmark, fallback artifact flow, dashboard launch, and safety
language.

- [ ] **Step 4: Verify Task 4**

Run: `.venv/bin/pytest tests/test_benchmarking.py::test_demo_scripts_makefile_and_readme_document_operating_flow -q`

Expected: PASS.

## Task 5: Status And Verification

**Files:**
- Modify: `IMPLEMENTATION_STATUS.md`

**Interfaces:**
- Consumes: completed Phase 8 verification output.

- [ ] **Step 1: Run focused tests**

Run: `.venv/bin/pytest tests/test_benchmarking.py -q`

Expected: PASS.

- [ ] **Step 2: Run required verification**

Run:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
make benchmark-smoke
.venv/bin/python -m fraud_demo generate-data --rows 260 --output /private/tmp/fraud-sentinel-phase8-full-smoke.csv --seed 42
.venv/bin/python -m fraud_demo run --input /private/tmp/fraud-sentinel-phase8-full-smoke.csv --run-id RUN_PHASE8_SMOKE --artifacts-dir /private/tmp/fraud-sentinel-phase8-artifacts --force
.venv/bin/python -m fraud_demo generate-data --rows 80 --output /private/tmp/fraud-sentinel-phase8-inbox/transactions_phase8_delta.csv --seed 43
.venv/bin/python -m fraud_demo monitor --inbox /private/tmp/fraud-sentinel-phase8-inbox --artifacts-dir /private/tmp/fraud-sentinel-phase8-artifacts --run-id RUN_PHASE8_MONITOR --force
.venv/bin/python -m fraud_demo validate-okf --bundle artifacts/okf_bundle
```

Inspect the smoke benchmark report fields:

```bash
.venv/bin/python -m json.tool /private/tmp/fraud-sentinel-benchmark-smoke-report.json
```

Confirm no external model/API calls and no dashboard raw CSV render reads:

```bash
rg -n "requests|httpx|openai|anthropic|api_key|http://|https://" src dashboard scripts tests Makefile pyproject.toml
rg -n "read_csv" dashboard src/fraud_demo
```

- [ ] **Step 3: Update status**

Update `IMPLEMENTATION_STATUS.md` Phase 8 row to Complete, append verification
output, note smoke benchmark report path, document full one-million-row benchmark
as manual if not run in this turn, and keep known limitations explicit.

- [ ] **Step 4: Final GitHub flow**

Run:

```bash
git status -sb
git diff --check
git add docs/superpowers/specs/2026-06-23-phase-8-performance-hardening-design.md docs/superpowers/plans/2026-06-23-phase-8-performance-hardening.md src/fraud_demo/benchmarking.py tests/test_benchmarking.py scripts/benchmark.sh scripts/demo_setup.sh scripts/demo_run.sh scripts/demo_monitor_delta.sh Makefile README.md IMPLEMENTATION_STATUS.md
git commit -m "feat: harden phase 8 benchmark and demo flow"
git push -u origin codex/phase-8-performance-hardening
```

Open a PR to `main`, merge it, switch to `main`, pull, and verify `HEAD` includes
the merge commit.
