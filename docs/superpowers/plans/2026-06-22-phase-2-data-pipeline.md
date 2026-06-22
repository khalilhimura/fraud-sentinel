# Phase 2 Data Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Phase 2 from the PRD: reproducible synthetic data generation, CSV ingestion and validation, normalized/rejected Parquet artifacts, data-quality profiling, and CLI wiring.

**Architecture:** Keep generator, ingestion, profiling, and manifest concerns separate. `run` coordinates the Phase 2 stages and records later stages as pending instead of pretending the full MVP exists.

**Tech Stack:** Python 3.12+, pandas, pyarrow, Pydantic, Typer, pytest, Ruff.

## Global Constraints

- Treat `PRD.md` as the source of truth.
- Do not send raw transaction data to a runtime LLM or external API.
- Keep detection logic deterministic; Phase 2 does not score fraud.
- Use synthetic or approved anonymized data only.
- Generated CSV, Parquet, logs, DuckDB files, and OKF outputs must remain ignored by Git.
- Validate on small fixtures before large data.
- Preserve source file names, source row numbers, and source fingerprints.

---

## Task 1: Synthetic Generator

**Files:**
- Modify: `src/fraud_demo/generate_data.py`
- Test: `tests/test_generate_data.py`

**Interfaces:**
- Produces: `SyntheticDataResult`
- Produces: `generate_synthetic_transactions(rows: int, output: Path | str, seed: int = 42, account_count: int | None = None, currency: str = "MYR") -> SyntheticDataResult`

- [ ] Write failing tests for row count, required columns, manifest scenarios, and reproducibility.
- [ ] Implement deterministic generator with required and recommended columns plus synthetic labels.
- [ ] Run `pytest tests/test_generate_data.py -q`.

## Task 2: Ingestion And Rejections

**Files:**
- Modify: `src/fraud_demo/ingest.py`
- Modify: `src/fraud_demo/privacy.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Produces: `IngestionResult`
- Produces: `ingest_transactions(input_paths: Sequence[Path | str], run_id: str, artifacts_dir: Path | str = "artifacts", force: bool = False) -> IngestionResult`

- [ ] Write failing tests for missing columns, normalization, invalid-row rejection, duplicate removal, and artifact paths.
- [ ] Implement CSV reading, schema checks, normalization, rejection rows, and Parquet writes.
- [ ] Run `pytest tests/test_ingest.py -q`.

## Task 3: Profiling And Manifests

**Files:**
- Modify: `src/fraud_demo/profile.py`
- Modify: `src/fraud_demo/manifests.py`
- Test: `tests/test_profile.py`

**Interfaces:**
- Produces: `profile_run(run_dir: Path | str, source_data_fingerprint: str) -> dict[str, object]`
- Produces: `write_run_manifest(run_dir: Path | str, manifest: dict[str, object]) -> Path`

- [ ] Write failing tests for `data_quality_report.json` and run manifest fields.
- [ ] Implement report generation from Phase 2 artifacts.
- [ ] Run `pytest tests/test_profile.py -q`.

## Task 4: CLI Wiring

**Files:**
- Modify: `src/fraud_demo/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes generator, ingestion, profiling, and manifest functions.
- Produces working `generate-data`, `profile`, and `run` commands for Phase 2.

- [ ] Update CLI tests to expect Phase 2 command success and artifact creation.
- [ ] Implement command wiring with elapsed-stage output.
- [ ] Run `pytest tests/test_cli.py -q`.

## Task 5: Status And Verification

**Files:**
- Modify: `IMPLEMENTATION_STATUS.md`

**Interfaces:**
- Consumes all Phase 2 tasks.
- Produces updated status and verification evidence.

- [ ] Run `.venv/bin/pytest -q`.
- [ ] Run `.venv/bin/ruff check .`.
- [ ] Run `.venv/bin/python -m fraud_demo generate-data --rows 100 --output /tmp/fraud-sentinel-smoke.csv --seed 42`.
- [ ] Run `.venv/bin/python -m fraud_demo run --input /tmp/fraud-sentinel-smoke.csv --run-id RUN_PHASE2_SMOKE --force`.
- [ ] Update `IMPLEMENTATION_STATUS.md` with results and limitations.
- [ ] Commit and push the Phase 2 branch.

## Self-Review

- Spec coverage: Covers PRD Phase 2 generator, CSV validation, normalized/rejected outputs, and data-quality report. DuckDB table persistence remains deferred because Phase 2 artifacts are Parquet-first and the PRD also allows Parquet artifacts; this will be revisited before performance hardening.
- Placeholder scan: No unbounded implementation placeholders in this plan.
- Type consistency: Public function names and return types match the tests planned for this phase.
