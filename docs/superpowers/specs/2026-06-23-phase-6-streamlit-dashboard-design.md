# Phase 6 Streamlit Dashboard Design

## Summary

Phase 6 turns the Phase 5 run artifacts into a local Streamlit dashboard for
repeat analyst review. The dashboard reads prepared Parquet files, JSON
manifests, validation reports, and OKF Markdown files only. It never reads the
raw source CSV during page render and never calls external models or APIs.

The interface is an operational fraud-analysis workspace: dense, scannable,
restrained, and built for repeated investigation. All analyst-facing language
continues to describe suspicious indicators requiring human review, not
confirmed fraud.

## Requirements

- Follow `PRD.md` Phase 6, FR-020, FR-021, FR-025, FR-027, FR-029, and
  AGENTS.md.
- Implement the existing Streamlit shell under `dashboard/`.
- Consume Phase 5 artifacts:
  `run_manifest.json`, `data_quality_report.json`, `normalized_transactions.parquet`,
  `rejected_rows.parquet`, `account_risk.parquet`, `rule_evidence.parquet`,
  `alerts.parquet`, `graph_nodes.parquet`, `graph_edges.parquet`,
  `clusters.parquet`, `okf_manifest.json`, `okf_validation_report.json`, and
  OKF Markdown concept files.
- Use `config/dashboard.yaml` for default artifact locations, cache TTL, graph
  node caps, graph edge caps, and counterparty caps.
- Use `st.cache_data` for artifact reads.
- Bound graph nodes and edges before passing data to Plotly or Streamlit.
- Display `okf_concept_id` paths from Phase 5 artifacts and preview matching
  Markdown where available.
- Include human-review disclaimers on the app landing page, Alert Queue, Account
  Investigation, Network Explorer, and OKF pages.
- Use Plotly for charts and graph views where useful.
- Do not introduce external model/API calls.

## Design Options

### Option A: Cached artifact reader plus view-model helpers

Create `dashboard/data.py` for cached artifact loading, validation, filtering,
metrics, joins, bounded graph selection, OKF summary, and Markdown preview.
Streamlit pages become thin renderers over these deterministic helpers.

Trade-offs: This is testable without launching Streamlit and keeps the page
modules simple. The data helper is larger, so it must be split by responsibility
inside the module.

### Option B: Page-local artifact loading

Each Streamlit page reads its own Parquet and JSON files directly.

Trade-offs: This is faster to write initially but duplicates error handling and
filter logic. It also makes the "no raw CSV read" and graph-bound guarantees
harder to prove.

### Option C: DuckDB-backed dashboard queries

Use the generated DuckDB database as the dashboard's primary read source and
query views for all pages.

Trade-offs: This aligns with analytical workflows, but Phase 6 explicitly
requires prepared Parquet and JSON artifacts. DuckDB can remain a future
optimization path for Phase 8.

## Decision

Use Option A. Phase 6 adds a cached artifact and view-model layer under
`dashboard/data.py`, then renders the six Streamlit pages from those helpers.
This keeps dashboard behavior deterministic, testable, and bounded before any
data reaches the browser.

## Visual Direction

The dashboard should feel like a case-review console, not a marketing site.
Use a compact layout with small metric cards, dense tables, restrained color,
and clear severity accents.

Palette:

- `ledger-ink` `#172026` for primary text.
- `case-paper` `#F7F8F5` for the app background.
- `panel-line` `#D7DED8` for separators and table borders.
- `review-amber` `#B87913` for human-review emphasis.
- `signal-red` `#B42318` for Critical severity.
- `network-teal` `#0E7C7B` for selected graph evidence.

Typography remains Streamlit-native for reliability, with concise labels and
utility-style captions. The signature element is a thin "provenance rail" near
the top of each page showing run ID, source fingerprint, and artifact status so
analysts always know what run they are reviewing.

## Artifact Discovery

The dashboard defaults to `config/dashboard.yaml`:

```text
default_artifacts_dir: artifacts
default_okf_bundle: artifacts/okf_bundle
cache_ttl_seconds: 60
network_limits.max_nodes: 500
network_limits.max_edges: 5000
network_limits.max_counterparties_per_account: 30
```

Pages use a sidebar text input for the artifacts directory or run directory.
If the path points at `artifacts/`, the newest run under `artifacts/runs/` is
selected by manifest `completed_at` when available and filesystem modification
time otherwise. If the path points directly at a run directory containing
`run_manifest.json`, that run is selected.

Missing optional artifacts render a concise warning. Missing required artifacts
do not crash imports or page load; affected sections render empty tables or
explicit missing-artifact messages.

## Data Contracts

`dashboard/data.py` exposes deterministic helpers:

```python
@dataclass(frozen=True)
class DashboardConfig:
    default_artifacts_dir: Path
    default_okf_bundle: Path
    cache_ttl_seconds: int
    max_nodes: int
    max_edges: int
    max_counterparties_per_account: int

@dataclass(frozen=True)
class DashboardArtifacts:
    run_dir: Path
    manifest: dict[str, Any]
    data_quality_report: dict[str, Any]
    frames: dict[str, pd.DataFrame]
    okf_manifest: dict[str, Any]
    okf_validation_report: dict[str, Any]
    missing_artifacts: tuple[str, ...]
```

Key helpers:

- `load_dashboard_config(path="config/dashboard.yaml") -> DashboardConfig`
- `resolve_run_dir(path, config) -> Path`
- `load_dashboard_artifacts(run_dir, config) -> DashboardArtifacts`
- `build_overview_metrics(artifacts) -> dict[str, Any]`
- `filter_alerts(alerts, filters) -> pd.DataFrame`
- `prepare_alert_download(alerts) -> bytes`
- `build_account_investigation(artifacts, account_id) -> dict[str, Any]`
- `build_bounded_graph(artifacts, filters, limits) -> dict[str, Any]`
- `build_okf_summary(artifacts) -> dict[str, Any]`
- `load_okf_markdown_preview(bundle, concept_id, max_chars=12000) -> str`

These helpers read Parquet, JSON, and Markdown only. They do not call
`pandas.read_csv`.

## Page Design

### App Landing

The landing page explains the current run and shows the human-review disclaimer,
run ID, source fingerprint, Phase 5 status, and links to the six dashboard
pages. It does not load raw source data.

### Overview

Displays valid rows, rejected rows, distinct accounts, High/Critical alert
counts, suspicious cluster count, suspicious transfer amount, run ID, and source
fingerprint. Charts show risk distribution, alerts over time, top suspicious
accounts, and top triggered rules.

### Alert Queue

Filters alerts by date range, risk level, minimum score, triggered rule, and
cluster. Country, bank, and channel are included only if those columns are
available in the prepared artifacts. The table uses PRD alert columns when
present and provides a CSV download of the filtered view.

### Account Investigation

Displays selected account risk score, severity, rule-by-rule evidence, incoming
and outgoing summaries, top counterparties, selected bounded graph evidence,
cluster membership, alert rows, and OKF concept path. The page repeats the
human-review disclaimer above the evidence.

### Network Explorer

Displays a bounded graph around a selected account or cluster. Controls include
depth, minimum amount, minimum transaction count, risk level, and node type.
Nodes size by risk score or degree, edges thicken by total amount or transaction
count, and hover text exposes amounts, counts, timestamps, and review notes.
The helper enforces node and edge caps before building the Plotly figure.

### OKF Knowledge Bundle

Displays OKF version, concept counts, internal link count, validation status,
validation warning count, validation warnings, most-linked concepts when
available, bundle path, selected concept Markdown preview, and concise Obsidian
opening instructions.

### Monitoring

Phase 6 monitoring reads the current single-run manifest only. It shows last
run, source files, source fingerprints, stage timings, failed/quarantined row
counts, and artifact paths. It does not implement Phase 7 rerun, delta, alert
change, or OKF update-log logic.

## Error Handling

- Missing `run_manifest.json`: page shows that no run is available.
- Missing Parquet artifact: page records the missing artifact and renders an
  empty DataFrame for affected sections.
- Invalid JSON report: page records a missing/invalid artifact warning and
  proceeds with an empty dictionary.
- Empty datasets: charts and tables render empty-state notices rather than
  exceptions.
- Graph cap truncation: graph views display the rendered node and edge counts
  and the configured cap.

## Testing

Use TDD for each behavior. Tests cover:

- Artifact loading without raw CSV reads.
- Missing artifact handling.
- Overview metrics.
- Alert filters and CSV download data preparation.
- Account investigation joins across risk, evidence, alerts, graph, clusters,
  and OKF concept IDs.
- Graph limit enforcement before Plotly rendering.
- OKF validation summary and Markdown preview.
- All dashboard pages importing without crashing.

## Out Of Scope

- Phase 7 monitoring rerun logic.
- Delta alert comparison beyond whatever single-run artifacts already contain.
- Full one-million-row raw CSV display.
- External model/API calls.
- Obsidian automation beyond instructions for opening `artifacts/okf_bundle/`.
