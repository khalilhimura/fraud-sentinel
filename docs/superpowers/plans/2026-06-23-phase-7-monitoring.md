# Phase 7 File-Based Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement deterministic file-based micro-batch monitoring for `python -m fraud_demo monitor --inbox data/incoming`.

**Architecture:** Add a monitoring orchestrator that discovers inbox CSVs, records processed-file state, builds a full current snapshot with the existing pipeline stages, compares current and prior alerts, refreshes OKF/dashboard artifacts, and updates run manifests. Keep dashboard changes limited to prepared monitoring artifacts.

**Tech Stack:** Python 3.12+, pandas, DuckDB, Typer, Pydantic-compatible dataclasses, Jinja2, NetworkX, Streamlit, Plotly, pytest, Ruff.

## Global Constraints

- Treat `PRD.md` as the source of truth.
- Follow AGENTS.md Phase 7 rules.
- Implement phases in PRD order.
- Keep fraud detection deterministic and rule-based.
- Do not send raw transaction data to external models or APIs.
- Use synthetic or approved anonymized data only.
- Label outputs as suspicious indicators requiring human review, not confirmed fraud.
- Preserve run provenance, configuration hashes, source fingerprints, file hashes, stage timings, and artifact paths.
- Do not generate one Markdown file per raw transaction.
- Keep dashboard graph rendering bounded by configuration.
- Never weaken or delete valid tests just to make the suite pass.

---

## File Structure

- Create `tests/test_monitoring.py`: TDD coverage for state, skip/force/retry, deduplication, alert deltas, manifest, OKF log, CLI paths, and dashboard delta helpers.
- Modify `src/fraud_demo/monitoring.py`: processed-file state models, file discovery, snapshot orchestration, alert comparison, summary/log writes, and public `process_inbox`.
- Modify `src/fraud_demo/cli.py`: replace the Phase 7 stub with the real monitor command and progress output.
- Modify `src/fraud_demo/manifests.py`: add a Phase 7 manifest extender.
- Modify `dashboard/data.py`: load `monitoring_summary.json` and expose `build_monitoring_summary`.
- Modify `dashboard/pages/6_Monitoring.py`: render prepared monitoring delta data.
- Modify `IMPLEMENTATION_STATUS.md`: record Phase 7 completion notes, assumptions, verification output, and blockers.

## Task 1: Processed-File State And File Discovery

**Files:**
- Create: `tests/test_monitoring.py`
- Modify: `src/fraud_demo/monitoring.py`

**Interfaces:**
- Produces: `ProcessedFileRecord`
- Produces: `load_processed_state(path: Path | str) -> list[ProcessedFileRecord]`
- Produces: `write_processed_state(path: Path | str, records: Sequence[ProcessedFileRecord]) -> Path`
- Produces: `discover_inbox_files(inbox: Path | str) -> list[Path]`
- Produces: `select_eligible_files(files: Sequence[Path], records: Sequence[ProcessedFileRecord], force: bool = False) -> tuple[list[InboxFile], list[InboxFile]]`

- [ ] **Step 1: Write failing state and discovery tests**

```python
def test_processed_file_state_creation_and_update(tmp_path):
    path = tmp_path / "processed_files.json"
    record = ProcessedFileRecord(
        file_path="/tmp/transactions_001.csv",
        file_sha256="a" * 64,
        first_seen_at="2026-06-23T00:00:00+00:00",
        processed_at="2026-06-23T00:01:00+00:00",
        run_id="RUN_MONITOR_20260623_000100",
        row_count=2,
        status="completed",
        error_message=None,
    )
    write_processed_state(path, [record])
    loaded = load_processed_state(path)
    assert loaded == [record]
```

```python
def test_discover_inbox_files_only_returns_transaction_csvs(tmp_path):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    (inbox / "transactions_001.csv").write_text("transaction_id\nTX1\n", encoding="utf-8")
    (inbox / "notes.csv").write_text("ignored\n", encoding="utf-8")
    assert [path.name for path in discover_inbox_files(inbox)] == ["transactions_001.csv"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/test_monitoring.py::test_processed_file_state_creation_and_update tests/test_monitoring.py::test_discover_inbox_files_only_returns_transaction_csvs -q`

Expected: FAIL because monitoring state helpers are missing.

- [ ] **Step 3: Implement minimal state and discovery helpers**

Implement immutable dataclasses, deterministic JSON writes with `sort_keys=True`,
empty-state loading, inbox existence validation, SHA-256 calculation via
`fraud_demo.config.file_sha256`, and path-sorted discovery.

- [ ] **Step 4: Verify Task 1**

Run: `.venv/bin/pytest tests/test_monitoring.py::test_processed_file_state_creation_and_update tests/test_monitoring.py::test_discover_inbox_files_only_returns_transaction_csvs -q`

Expected: PASS.

## Task 2: Idempotency, Force, And Failed Retry

**Files:**
- Modify: `tests/test_monitoring.py`
- Modify: `src/fraud_demo/monitoring.py`

**Interfaces:**
- Consumes: `select_eligible_files`
- Produces: completed-hash skip behavior and retryable failed hashes.

- [ ] **Step 1: Write failing idempotency tests**

```python
def test_completed_file_hash_is_skipped_without_force(tmp_path):
    source = _write_transactions_csv(tmp_path / "incoming" / "transactions_001.csv", ["TX1"])
    digest = file_sha256(source)
    records = [_state_record(source, digest, status="completed", run_id="RUN_OLD")]
    eligible, skipped = select_eligible_files([source], records, force=False)
    assert eligible == []
    assert [item.file_sha256 for item in skipped] == [digest]
```

```python
def test_force_reprocesses_completed_file_hash(tmp_path):
    source = _write_transactions_csv(tmp_path / "incoming" / "transactions_001.csv", ["TX1"])
    digest = file_sha256(source)
    records = [_state_record(source, digest, status="completed", run_id="RUN_OLD")]
    eligible, skipped = select_eligible_files([source], records, force=True)
    assert [item.path for item in eligible] == [source]
    assert skipped == []
```

```python
def test_failed_file_hash_is_retryable(tmp_path):
    source = _write_transactions_csv(tmp_path / "incoming" / "transactions_001.csv", ["TX1"])
    digest = file_sha256(source)
    records = [_state_record(source, digest, status="failed", run_id="RUN_OLD")]
    eligible, skipped = select_eligible_files([source], records, force=False)
    assert [item.path for item in eligible] == [source]
    assert skipped == []
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/test_monitoring.py::test_completed_file_hash_is_skipped_without_force tests/test_monitoring.py::test_force_reprocesses_completed_file_hash tests/test_monitoring.py::test_failed_file_hash_is_retryable -q`

Expected: FAIL until eligibility logic exists.

- [ ] **Step 3: Implement eligibility logic**

Build a set of completed hashes, skip those only when `force` is false, and
return `InboxFile(path, file_sha256, first_seen_at)` objects with deterministic
path ordering.

- [ ] **Step 4: Verify Task 2**

Run: `.venv/bin/pytest tests/test_monitoring.py::test_completed_file_hash_is_skipped_without_force tests/test_monitoring.py::test_force_reprocesses_completed_file_hash tests/test_monitoring.py::test_failed_file_hash_is_retryable -q`

Expected: PASS.

## Task 3: Monitoring Snapshot Orchestration

**Files:**
- Modify: `tests/test_monitoring.py`
- Modify: `src/fraud_demo/monitoring.py`
- Modify: `src/fraud_demo/manifests.py`

**Interfaces:**
- Produces: `MonitoringResult`
- Produces: `process_inbox(inbox: Path | str, artifacts_dir: Path | str = "artifacts", force: bool = False, run_id: str | None = None) -> MonitoringResult`
- Produces: `build_phase7_manifest(phase5_manifest: dict[str, Any], monitoring_result: Any, stage_timings_seconds: dict[str, float]) -> dict[str, Any]`

- [ ] **Step 1: Write failing snapshot and manifest tests**

```python
def test_monitoring_run_deduplicates_transaction_ids_across_files(tmp_path):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    _write_transactions_csv(inbox / "transactions_001.csv", ["TX_DUP", "TX_KEEP_A"])
    _write_transactions_csv(inbox / "transactions_002.csv", ["TX_DUP", "TX_KEEP_B"])
    result = process_inbox(
        inbox,
        artifacts_dir=tmp_path / "artifacts",
        run_id="RUN_MONITOR_TEST",
        force=False,
    )
    normalized = pd.read_parquet(result.run_dir / "normalized_transactions.parquet")
    rejected = pd.read_parquet(result.run_dir / "rejected_rows.parquet")
    assert sorted(normalized["transaction_id"].tolist()) == ["TX_DUP", "TX_KEEP_A", "TX_KEEP_B"]
    assert "duplicate_transaction_id" in set(rejected["rejection_code"])
```

```python
def test_monitoring_manifest_records_phase7_fields_and_timings(tmp_path):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    _write_transactions_csv(inbox / "transactions_001.csv", ["TX1", "TX2"])
    result = process_inbox(inbox, artifacts_dir=tmp_path / "artifacts", run_id="RUN_MONITOR_MANIFEST")
    manifest = json.loads((result.run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "phase7_complete"
    assert manifest["phase_status"]["phase7_monitoring"] == "complete"
    assert manifest["processed_file_count"] == 1
    assert "monitor_discovery" in manifest["stage_timings_seconds"]
    assert "alert_comparison" in manifest["stage_timings_seconds"]
    assert manifest["artifact_paths"]["processed_files_state"].endswith("processed_files.json")
    assert manifest["artifact_paths"]["alert_changes"].endswith("alert_changes.parquet")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/test_monitoring.py::test_monitoring_run_deduplicates_transaction_ids_across_files tests/test_monitoring.py::test_monitoring_manifest_records_phase7_fields_and_timings -q`

Expected: FAIL until `process_inbox` orchestrates the full pipeline.

- [ ] **Step 3: Implement full snapshot orchestration**

Use existing modules in order: `ingest_transactions`, `profile_run`,
`compute_account_features`, `score_accounts`, `generate_alerts`,
`build_graph_artifacts`, `identify_clusters`, `export_okf_bundle`, and
`validate_okf_bundle`. Generate run IDs as `RUN_MONITOR_YYYYMMDD_HHMMSS` when
not provided. Measure and store stage timings.

- [ ] **Step 4: Implement Phase 7 manifest helper**

Extend the Phase 5 manifest with Phase 7 fields and monitoring artifact paths.
Keep Phase 2 through Phase 5 provenance intact.

- [ ] **Step 5: Verify Task 3**

Run: `.venv/bin/pytest tests/test_monitoring.py::test_monitoring_run_deduplicates_transaction_ids_across_files tests/test_monitoring.py::test_monitoring_manifest_records_phase7_fields_and_timings -q`

Expected: PASS.

## Task 4: Alert Comparison And Monitoring Logs

**Files:**
- Modify: `tests/test_monitoring.py`
- Modify: `src/fraud_demo/monitoring.py`

**Interfaces:**
- Produces: `compare_alerts(prior_alerts: pd.DataFrame, current_alerts: pd.DataFrame, run_id: str, prior_run_id: str | None) -> pd.DataFrame`
- Produces: `write_monitoring_summary(...) -> Path`
- Produces: `append_monitoring_log(...) -> Path`

- [ ] **Step 1: Write failing alert comparison test**

```python
def test_alert_comparison_categories():
    prior = pd.DataFrame(
        [
            _alert("RUN_OLD", "ACC_NEW_HIGH", 55, "High"),
            _alert("RUN_OLD", "ACC_UP", 55, "High"),
            _alert("RUN_OLD", "ACC_DOWN", 85, "Critical"),
            _alert("RUN_OLD", "ACC_SAME", 55, "High"),
            _alert("RUN_OLD", "ACC_RESOLVED", 55, "High"),
        ]
    )
    current = pd.DataFrame(
        [
            _alert("RUN_NEW", "ACC_BRAND_NEW", 55, "High"),
            _alert("RUN_NEW", "ACC_UP", 85, "Critical"),
            _alert("RUN_NEW", "ACC_DOWN", 55, "High"),
            _alert("RUN_NEW", "ACC_SAME", 55, "High"),
            _alert("RUN_NEW", "ACC_NEW_HIGH", 55, "High"),
        ]
    )
    changes = compare_alerts(prior, current, run_id="RUN_NEW", prior_run_id="RUN_OLD")
    assert changes.set_index("account_id")["change_category"].to_dict() == {
        "ACC_BRAND_NEW": "new",
        "ACC_UP": "severity_increased",
        "ACC_DOWN": "severity_decreased",
        "ACC_SAME": "unchanged",
        "ACC_NEW_HIGH": "unchanged",
        "ACC_RESOLVED": "resolved_below_threshold",
    }
```

```python
def test_okf_monitoring_log_is_appended(tmp_path):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    _write_transactions_csv(inbox / "transactions_001.csv", ["TX1"])
    result = process_inbox(inbox, artifacts_dir=tmp_path / "artifacts", run_id="RUN_LOG")
    log_path = tmp_path / "artifacts" / "monitoring" / "monitoring_log.jsonl"
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert entries[-1]["run_id"] == "RUN_LOG"
    assert "alert_change_counts" in entries[-1]
    assert (Path("artifacts") / "okf_bundle" / "log.md").exists()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/test_monitoring.py::test_alert_comparison_categories tests/test_monitoring.py::test_okf_monitoring_log_is_appended -q`

Expected: FAIL until comparison and log writes exist.

- [ ] **Step 3: Implement comparison and logs**

Write `alert_changes.parquet`, `monitoring_summary.json`, append
`monitoring_log.jsonl`, and append a concise monitoring section to
`artifacts/okf_bundle/log.md` after OKF export. Use human-review language in
the notes.

- [ ] **Step 4: Verify Task 4**

Run: `.venv/bin/pytest tests/test_monitoring.py::test_alert_comparison_categories tests/test_monitoring.py::test_okf_monitoring_log_is_appended -q`

Expected: PASS.

## Task 5: CLI Monitor Command

**Files:**
- Modify: `tests/test_monitoring.py`
- Modify: `tests/test_cli.py`
- Modify: `src/fraud_demo/cli.py`

**Interfaces:**
- Consumes: `process_inbox`
- Produces: real `monitor` Typer command with progress output and non-zero hard failures.

- [ ] **Step 1: Write failing CLI tests**

```python
def test_cli_monitor_success_outputs_paths(tmp_path):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    _write_transactions_csv(inbox / "transactions_001.csv", ["TX1", "TX2"])
    result = CliRunner().invoke(
        app,
        ["monitor", "--inbox", str(inbox), "--artifacts-dir", str(tmp_path / "artifacts")],
    )
    assert result.exit_code == 0
    assert "Monitoring complete" in result.output
    assert "processed_files.json" in result.output
    assert "alert_changes.parquet" in result.output
```

```python
def test_cli_monitor_failure_returns_non_zero_for_bad_file(tmp_path):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    (inbox / "transactions_bad.csv").write_text("wrong\nvalue\n", encoding="utf-8")
    result = CliRunner().invoke(
        app,
        ["monitor", "--inbox", str(inbox), "--artifacts-dir", str(tmp_path / "artifacts")],
    )
    assert result.exit_code != 0
    assert "Monitoring failed" in result.output
```

- [ ] **Step 2: Run CLI tests to verify failure**

Run: `.venv/bin/pytest tests/test_monitoring.py::test_cli_monitor_success_outputs_paths tests/test_monitoring.py::test_cli_monitor_failure_returns_non_zero_for_bad_file -q`

Expected: FAIL because the CLI still exits with the Phase 7 stub.

- [ ] **Step 3: Implement CLI command**

Add `--artifacts-dir`, `--run-id`, and `--force` options, call
`process_inbox`, print stage progress and elapsed time from the result, print
output paths on completion, and convert hard monitoring exceptions into
`typer.Exit(1)`.

- [ ] **Step 4: Verify Task 5**

Run: `.venv/bin/pytest tests/test_monitoring.py::test_cli_monitor_success_outputs_paths tests/test_monitoring.py::test_cli_monitor_failure_returns_non_zero_for_bad_file -q`

Expected: PASS.

## Task 6: Dashboard Monitoring Delta Data

**Files:**
- Modify: `tests/test_dashboard.py`
- Modify: `dashboard/data.py`
- Modify: `dashboard/pages/6_Monitoring.py`

**Interfaces:**
- Produces: `build_monitoring_summary(artifacts: DashboardArtifacts) -> dict[str, object]`

- [ ] **Step 1: Write failing dashboard helper test**

```python
def test_monitoring_summary_uses_prepared_delta_artifacts(tmp_path, monkeypatch):
    run_dir = _write_dashboard_run(tmp_path)
    pd.DataFrame(
        [
            {
                "run_id": "RUN_DASH",
                "prior_run_id": "RUN_OLD",
                "account_id": "ACC_MULE",
                "change_category": "severity_increased",
                "current_risk_level": "Critical",
                "current_risk_score": 85,
            }
        ]
    ).to_parquet(run_dir / "alert_changes.parquet", index=False)
    (run_dir / "monitoring_summary.json").write_text(
        json.dumps({"processed_file_count": 1, "skipped_file_count": 0, "new_transaction_count": 2}),
        encoding="utf-8",
    )
    config = _write_dashboard_config(tmp_path)
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("raw CSV read")))
    summary = build_monitoring_summary(load_dashboard_artifacts(run_dir, config))
    assert summary["change_counts"]["severity_increased"] == 1
    assert summary["severity_increased_accounts"]["account_id"].tolist() == ["ACC_MULE"]
    assert summary["new_transaction_count"] == 2
```

- [ ] **Step 2: Run dashboard test to verify failure**

Run: `.venv/bin/pytest tests/test_dashboard.py::test_monitoring_summary_uses_prepared_delta_artifacts -q`

Expected: FAIL until helper exists.

- [ ] **Step 3: Implement helper and page rendering**

Load optional `monitoring_summary.json`, summarize `alert_changes.parquet`,
show severity-increased accounts, processed/skipped/failed files, OKF log path,
stage timings, and artifact paths. Keep dashboard reads limited to Parquet,
JSON, and Markdown.

- [ ] **Step 4: Verify Task 6**

Run: `.venv/bin/pytest tests/test_dashboard.py::test_monitoring_summary_uses_prepared_delta_artifacts -q`

Expected: PASS.

## Task 7: Status Docs And Full Verification

**Files:**
- Modify: `IMPLEMENTATION_STATUS.md`

**Interfaces:**
- Produces: Phase 7 status, assumptions, verification output, and blockers.

- [ ] **Step 1: Update implementation status**

Record Phase 7 complete, implementation assumptions, verification commands,
smoke-run results, and any residual notes.

- [ ] **Step 2: Run full test and lint verification**

Run: `.venv/bin/pytest -q`

Expected: all tests pass.

Run: `.venv/bin/ruff check .`

Expected: all checks pass.

- [ ] **Step 3: Run manual monitoring smoke**

Run:

```bash
.venv/bin/python -m fraud_demo generate-data --rows 240 --output /private/tmp/fraud-sentinel-phase7-baseline.csv --seed 42
.venv/bin/python -m fraud_demo run --input /private/tmp/fraud-sentinel-phase7-baseline.csv --run-id RUN_PHASE7_BASELINE --artifacts-dir /private/tmp/fraud-sentinel-phase7-artifacts --force
mkdir -p /private/tmp/fraud-sentinel-phase7-inbox
.venv/bin/python -m fraud_demo generate-data --rows 80 --output /private/tmp/fraud-sentinel-phase7-inbox/transactions_delta.csv --seed 43
.venv/bin/python -m fraud_demo monitor --inbox /private/tmp/fraud-sentinel-phase7-inbox --artifacts-dir /private/tmp/fraud-sentinel-phase7-artifacts --run-id RUN_PHASE7_MONITOR --force
```

Expected: monitor writes processed-file state, a new run manifest, alert deltas,
OKF monitoring log entries, and dashboard-readable monitoring artifacts.

- [ ] **Step 4: Confirm no external model/API calls**

Run: `rg -n "requests|httpx|openai|anthropic|api_key|read_csv" src/fraud_demo dashboard tests`

Expected: no external model/API calls; dashboard raw CSV reads remain absent
outside test guards, and production `read_csv` occurrences are ingestion-only.

- [ ] **Step 5: Commit**

Run:

```bash
git add docs/superpowers/specs/2026-06-23-phase-7-monitoring-design.md docs/superpowers/plans/2026-06-23-phase-7-monitoring.md tests/test_monitoring.py tests/test_cli.py tests/test_dashboard.py src/fraud_demo/monitoring.py src/fraud_demo/cli.py src/fraud_demo/manifests.py dashboard/data.py dashboard/pages/6_Monitoring.py IMPLEMENTATION_STATUS.md
git commit -m "feat: implement phase 7 monitoring"
```

Expected: commit succeeds on `codex/phase-7-monitoring`.
