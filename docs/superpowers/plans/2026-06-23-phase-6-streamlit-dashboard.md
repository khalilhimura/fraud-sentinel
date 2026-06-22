# Phase 6 Streamlit Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 6 Streamlit dashboard over prepared Phase 5 artifacts.

**Architecture:** Add a cached `dashboard/data.py` layer that reads Parquet, JSON, and OKF Markdown artifacts, derives deterministic view models, and enforces graph limits before rendering. Keep Streamlit page modules thin and operational, with Plotly charts and explicit human-review language.

**Tech Stack:** Python 3.12+, pandas, PyYAML, Streamlit, Plotly, pytest, Ruff.

## Global Constraints

- Treat `PRD.md` as the source of truth.
- Follow AGENTS.md Phase 6 rules.
- Implement phases in PRD order.
- Use prepared Parquet, JSON manifest/report, and OKF Markdown artifacts only on page render.
- Do not read raw CSV files on dashboard page render.
- Use `st.cache_data` for artifact loading.
- Respect `config/dashboard.yaml` graph node, edge, and counterparty limits.
- Bound graph data before sending it to the browser.
- Label outputs as suspicious indicators requiring human review, not confirmed fraud.
- Display `okf_concept_id` links or paths from Phase 5 artifacts.
- Do not introduce external model/API calls.
- Do not implement full Phase 7 monitoring/rerun logic.
- Never weaken or delete valid tests just to make the suite pass.

---

## File Structure

- Create `dashboard/data.py`: cached artifact loading, config model, missing-artifact handling, overview metrics, alert filters, account investigation joins, bounded graph view models, OKF summaries, and Markdown previews.
- Modify `dashboard/common.py`: shared human-review copy, Streamlit shell helpers, severity ordering, compact styling helpers.
- Modify `dashboard/app.py`: landing page with run selector, provenance rail, disclaimer, and page links.
- Modify `dashboard/pages/1_Overview.py`: overview metrics, charts, and top tables.
- Modify `dashboard/pages/2_Alerts.py`: alert filters, PRD columns, and CSV download.
- Modify `dashboard/pages/3_Account_Investigation.py`: account selector, evidence, counterparties, bounded graph evidence, cluster membership, and OKF path.
- Modify `dashboard/pages/4_Network_Explorer.py`: bounded graph controls and Plotly network figure.
- Modify `dashboard/pages/5_OKF_Knowledge_Bundle.py`: OKF summary, validation warnings, Markdown preview, and Obsidian instructions.
- Modify `dashboard/pages/6_Monitoring.py`: single-run manifest monitoring.
- Add `tests/test_dashboard.py`: dashboard data and page-import coverage.
- Modify `IMPLEMENTATION_STATUS.md`: Phase 6 status, assumptions, verification output, and blockers.

## Task 1: Cached Artifact Loader And Overview Metrics

**Files:**
- Create: `dashboard/data.py`
- Modify: `dashboard/common.py`
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Produces: `DashboardConfig`
- Produces: `DashboardArtifacts`
- Produces: `load_dashboard_config(path: Path | str = "config/dashboard.yaml") -> DashboardConfig`
- Produces: `resolve_run_dir(path: Path | str, config: DashboardConfig) -> Path`
- Produces: `load_dashboard_artifacts(run_dir: Path | str, config: DashboardConfig) -> DashboardArtifacts`
- Produces: `build_overview_metrics(artifacts: DashboardArtifacts) -> dict[str, object]`

- [ ] **Step 1: Write failing loader and overview tests**

Add tests like:

```python
def test_dashboard_artifact_loading_never_reads_raw_csv(tmp_path, monkeypatch):
    run_dir = _write_dashboard_run(tmp_path)
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("raw CSV read")))
    artifacts = load_dashboard_artifacts(run_dir, load_dashboard_config(tmp_path / "dashboard.yaml"))
    assert artifacts.manifest["run_id"] == "RUN_DASH"
    assert len(artifacts.frames["alerts"]) == 2
    assert artifacts.missing_artifacts == ()

def test_overview_metrics_use_manifest_and_prepared_frames(tmp_path):
    artifacts = load_dashboard_artifacts(_write_dashboard_run(tmp_path), _write_dashboard_config(tmp_path))
    metrics = build_overview_metrics(artifacts)
    assert metrics["valid_row_count"] == 10
    assert metrics["rejected_row_count"] == 1
    assert metrics["high_critical_alert_count"] == 2
    assert metrics["suspicious_transfer_amount"] == 3000.0
```

- [ ] **Step 2: Run loader tests to verify failure**

Run: `.venv/bin/pytest tests/test_dashboard.py::test_dashboard_artifact_loading_never_reads_raw_csv tests/test_dashboard.py::test_overview_metrics_use_manifest_and_prepared_frames -q`

Expected: FAIL because `dashboard.data` does not exist.

- [ ] **Step 3: Implement minimal loader and metrics**

Create `DashboardConfig`, `DashboardArtifacts`, cached JSON and Parquet readers using `@st.cache_data`, artifact path resolution from manifest/default filenames, empty DataFrame fallbacks, missing artifact collection, and overview metric aggregation.

- [ ] **Step 4: Run loader tests to verify pass**

Run: `.venv/bin/pytest tests/test_dashboard.py::test_dashboard_artifact_loading_never_reads_raw_csv tests/test_dashboard.py::test_overview_metrics_use_manifest_and_prepared_frames -q`

Expected: PASS.

## Task 2: Alert Queue And Account Investigation Data

**Files:**
- Modify: `dashboard/data.py`
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Produces: `filter_alerts(alerts: pd.DataFrame, filters: AlertFilters | Mapping[str, object]) -> pd.DataFrame`
- Produces: `prepare_alert_download(alerts: pd.DataFrame) -> bytes`
- Produces: `build_account_investigation(artifacts: DashboardArtifacts, account_id: str) -> dict[str, object]`

- [ ] **Step 1: Write failing alert filter/download tests**

```python
def test_alert_filters_and_download_prepare_prd_columns(tmp_path):
    artifacts = load_dashboard_artifacts(_write_dashboard_run(tmp_path), _write_dashboard_config(tmp_path))
    filtered = filter_alerts(
        artifacts.frames["alerts"],
        {
            "risk_levels": ["Critical"],
            "min_score": 80,
            "triggered_rule": "rapid_pass_through",
            "cluster_id": "CLUSTER_RUN_DASH_001",
        },
    )
    assert filtered["alert_id"].tolist() == ["ALERT_RUN_DASH_ACC_MULE"]
    assert b"alert_id,account_id,risk_score" in prepare_alert_download(filtered)
```

- [ ] **Step 2: Run alert tests to verify failure**

Run: `.venv/bin/pytest tests/test_dashboard.py::test_alert_filters_and_download_prepare_prd_columns -q`

Expected: FAIL until filter/download helpers exist.

- [ ] **Step 3: Implement alert helpers**

Parse list-like `triggered_rule_ids`, apply date/risk/min-score/rule/cluster filters, preserve available PRD columns first, and return UTF-8 CSV bytes for download.

- [ ] **Step 4: Write failing account investigation join test**

```python
def test_account_investigation_joins_evidence_counterparties_cluster_and_okf(tmp_path):
    artifacts = load_dashboard_artifacts(_write_dashboard_run(tmp_path), _write_dashboard_config(tmp_path))
    investigation = build_account_investigation(artifacts, "ACC_MULE")
    assert investigation["account"]["account_id"] == "ACC_MULE"
    assert investigation["okf_concept_id"] == "accounts/ACC_MULE"
    assert investigation["cluster"]["cluster_id"] == "CLUSTER_RUN_DASH_001"
    assert investigation["incoming_summary"]["transaction_count"] == 1
    assert investigation["outgoing_summary"]["transaction_count"] == 1
    assert investigation["rule_evidence"]["rule_id"].tolist() == ["rapid_pass_through"]
```

- [ ] **Step 5: Run account join test to verify failure**

Run: `.venv/bin/pytest tests/test_dashboard.py::test_account_investigation_joins_evidence_counterparties_cluster_and_okf -q`

Expected: FAIL until account join helper exists.

- [ ] **Step 6: Implement account investigation helper**

Join account risk, alerts, triggered rule evidence, incoming/outgoing transfer edges, top counterparties capped by config, cluster row, and OKF concept path.

- [ ] **Step 7: Run Task 2 tests**

Run: `.venv/bin/pytest tests/test_dashboard.py::test_alert_filters_and_download_prepare_prd_columns tests/test_dashboard.py::test_account_investigation_joins_evidence_counterparties_cluster_and_okf -q`

Expected: PASS.

## Task 3: Bounded Graph And OKF View Models

**Files:**
- Modify: `dashboard/data.py`
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Produces: `build_bounded_graph(artifacts: DashboardArtifacts, filters: Mapping[str, object]) -> dict[str, object]`
- Produces: `build_okf_summary(artifacts: DashboardArtifacts) -> dict[str, object]`
- Produces: `load_okf_markdown_preview(bundle: Path | str, concept_id: str, max_chars: int = 12000) -> str`

- [ ] **Step 1: Write failing graph cap test**

```python
def test_bounded_graph_enforces_dashboard_limits_before_render(tmp_path):
    artifacts = load_dashboard_artifacts(_write_dashboard_run(tmp_path, extra_graph_nodes=20), _write_dashboard_config(tmp_path, max_nodes=3, max_edges=2))
    graph = build_bounded_graph(artifacts, {"account_id": "ACC_MULE", "depth": 2})
    assert len(graph["nodes"]) <= 3
    assert len(graph["edges"]) <= 2
    assert graph["limits"]["max_nodes"] == 3
```

- [ ] **Step 2: Run graph cap test to verify failure**

Run: `.venv/bin/pytest tests/test_dashboard.py::test_bounded_graph_enforces_dashboard_limits_before_render -q`

Expected: FAIL until graph helper exists.

- [ ] **Step 3: Implement bounded graph helper**

Filter by selected account or cluster, depth, minimum amount, minimum transaction count, risk level, and node type. Sort by suspicion, score, total amount, and edge count, then cap nodes and edges before returning dictionaries for Plotly.

- [ ] **Step 4: Write failing OKF summary/preview test**

```python
def test_okf_summary_and_markdown_preview(tmp_path):
    artifacts = load_dashboard_artifacts(_write_dashboard_run(tmp_path), _write_dashboard_config(tmp_path))
    summary = build_okf_summary(artifacts)
    assert summary["okf_version"] == "0.1"
    assert summary["concept_count"] == 4
    assert summary["validation_valid"] is True
    preview = load_okf_markdown_preview(artifacts.okf_bundle_path, "accounts/ACC_MULE")
    assert "Account ACC_MULE" in preview
```

- [ ] **Step 5: Run OKF test to verify failure**

Run: `.venv/bin/pytest tests/test_dashboard.py::test_okf_summary_and_markdown_preview -q`

Expected: FAIL until OKF helpers exist.

- [ ] **Step 6: Implement OKF helpers**

Summarize `okf_manifest.json`, `okf_validation_report.json`, warnings, concept counts, link count, and bundle path. Resolve concept IDs to Markdown paths with containment checks and return a bounded preview string.

- [ ] **Step 7: Run Task 3 tests**

Run: `.venv/bin/pytest tests/test_dashboard.py::test_bounded_graph_enforces_dashboard_limits_before_render tests/test_dashboard.py::test_okf_summary_and_markdown_preview -q`

Expected: PASS.

## Task 4: Streamlit Pages

**Files:**
- Modify: `dashboard/app.py`
- Modify: `dashboard/common.py`
- Modify: `dashboard/pages/1_Overview.py`
- Modify: `dashboard/pages/2_Alerts.py`
- Modify: `dashboard/pages/3_Account_Investigation.py`
- Modify: `dashboard/pages/4_Network_Explorer.py`
- Modify: `dashboard/pages/5_OKF_Knowledge_Bundle.py`
- Modify: `dashboard/pages/6_Monitoring.py`
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Consumes all helpers from `dashboard.data`.
- Produces import-safe Streamlit page modules.

- [ ] **Step 1: Write failing page-import test**

```python
def test_dashboard_pages_import_without_crashing():
    for path in sorted(Path("dashboard/pages").glob("*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
```

- [ ] **Step 2: Run page-import test to verify baseline**

Run: `.venv/bin/pytest tests/test_dashboard.py::test_dashboard_pages_import_without_crashing -q`

Expected: PASS for existing page stubs or FAIL if Streamlit import setup needs adjustment.

- [ ] **Step 3: Implement page renderers**

Use shared sidebar/run loading helpers, provenance rail, compact page headings, human-review notices, Plotly charts, alert download buttons, account selectors, bounded graph figures, OKF preview, and monitoring manifest tables.

- [ ] **Step 4: Run page-import test after implementation**

Run: `.venv/bin/pytest tests/test_dashboard.py::test_dashboard_pages_import_without_crashing -q`

Expected: PASS.

## Task 5: Status, Smoke Run, Visual QA, Publish

**Files:**
- Modify: `IMPLEMENTATION_STATUS.md`

**Interfaces:**
- Consumes all Phase 6 implementation outputs.
- Produces updated status and verification evidence.

- [ ] **Step 1: Run full tests**

Run: `.venv/bin/pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run Ruff**

Run: `.venv/bin/ruff check .`

Expected: all checks pass.

- [ ] **Step 3: Generate Phase 6 smoke artifacts**

Run: `.venv/bin/python -m fraud_demo generate-data --rows 220 --output /private/tmp/fraud-sentinel-phase6-smoke.csv --seed 42`

Expected: command exits 0 and writes the CSV plus scenario manifest.

Run: `.venv/bin/python -m fraud_demo run --input /private/tmp/fraud-sentinel-phase6-smoke.csv --run-id RUN_PHASE6_SMOKE --artifacts-dir /private/tmp/fraud-sentinel-phase6-artifacts --force`

Expected: command exits 0, prints `Phase 5 complete`, writes Phase 5 artifacts, and refreshes `artifacts/okf_bundle`.

- [ ] **Step 4: Start Streamlit and verify pages**

Run: `.venv/bin/streamlit run dashboard/app.py --server.headless true --server.port 8501`

Expected: server starts locally. Open `http://localhost:8501`, visit all six pages, and capture a screenshot or equivalent browser QA evidence. Confirm pages render without raw CSV reads or unbounded graph rendering.

- [ ] **Step 5: Update implementation status**

Record Phase 6 as complete, list assumptions, verification commands, Streamlit/browser QA evidence, and any non-blocking warnings.

- [ ] **Step 6: Review, commit, push, PR, merge**

Run final verification, inspect `git diff`, request review before merge, commit as `feat: implement phase 6 dashboard`, push `codex/phase-6-dashboard`, open a PR to `main`, merge it, switch to `main`, pull, and verify `main` contains the merge and is clean.
