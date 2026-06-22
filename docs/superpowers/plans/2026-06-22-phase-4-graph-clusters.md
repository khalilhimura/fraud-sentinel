# Phase 4 Graph And Clusters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Phase 4 filtered graph artifacts, suspicious connected clusters, bounded cycle enrichment, cluster ID propagation, and manifest integration.

**Architecture:** `graph_builder.py` reads Phase 3 run artifacts and writes bounded account graph nodes plus aggregated transfer edges. `clusters.py` reads only the bounded graph artifacts, runs NetworkX connected components and bounded cycle detection, then rewrites graph/risk/alert artifacts with cluster IDs. `cli.py` orchestrates the new stages and `manifests.py` records Phase 4 completion.

**Tech Stack:** Python 3.12+, pandas, pyarrow, DuckDB, NetworkX, Typer, pytest, Ruff.

## Global Constraints

- Treat `PRD.md` as the source of truth.
- Do not send raw transaction data to a runtime LLM or external API.
- Keep fraud detection deterministic and rule-based.
- Use synthetic or approved anonymized data only.
- Label outputs as suspicious indicators requiring human review, not confirmed fraud.
- Preserve run provenance, configuration hashes, source fingerprints, and stage timings.
- Do not generate one Markdown file per raw transaction.
- Keep graph rendering and NetworkX processing bounded by configuration.
- Do not create Markdown, OKF, or Obsidian files in Phase 4.
- Do not weaken or delete valid tests just to make the suite pass.

---

## File Structure

- Modify `src/fraud_demo/graph_builder.py`: filtered graph node construction, transfer edge aggregation, Parquet writes, DuckDB registration.
- Modify `src/fraud_demo/clusters.py`: connected components, bounded cycle enrichment, cluster summaries, cluster ID propagation, Parquet rewrites, DuckDB registration.
- Modify `src/fraud_demo/manifests.py`: Phase 4 manifest updater.
- Modify `src/fraud_demo/cli.py`: Phase 4 pipeline orchestration and output text.
- Create `tests/test_graph_builder.py`: graph build unit tests.
- Create `tests/test_clusters.py`: cluster unit tests.
- Modify `tests/test_cli.py`: Phase 4 CLI smoke assertions.
- Modify `IMPLEMENTATION_STATUS.md`: Phase 4 tracker, assumptions, and verification evidence.

## Task 1: Filtered Graph Builder

**Files:**
- Modify: `src/fraud_demo/graph_builder.py`
- Test: `tests/test_graph_builder.py`

**Interfaces:**
- Produces: `GraphBuildResult`
- Produces: `build_graph_artifacts(run_dir: Path | str, *, max_account_nodes: int = 500, max_context_accounts: int = 500, max_edges: int = 5_000, max_counterparties_per_account: int = 30, max_sample_transactions: int = 5) -> GraphBuildResult`

- [ ] **Step 1: Write failing graph aggregation test**

Create `tests/test_graph_builder.py` with fixtures that write `normalized_transactions.parquet`, `account_risk.parquet`, `alerts.parquet`, and a minimal `transactions.duckdb`. Include two transfers from `ACC_A` to High-risk `ACC_MULE`, one transfer from `ACC_MULE` to `ACC_OUT`, and an unrelated low-risk transfer.

Assert:

```python
result = build_graph_artifacts(run_dir, max_sample_transactions=1)
nodes = pd.read_parquet(result.graph_nodes_path)
edges = pd.read_parquet(result.graph_edges_path)

transfer_edges = edges.loc[edges["edge_type"].eq("TRANSFERRED_TO")]
edge = transfer_edges.loc[
    transfer_edges["source_node_id"].eq("ACC_A")
    & transfer_edges["target_node_id"].eq("ACC_MULE")
].iloc[0]

assert result.run_id == "RUN_GRAPH"
assert set(nodes["node_id"]) >= {"ACC_MULE", "ACC_A", "ACC_OUT"}
assert "ACC_LOW_1" not in set(nodes["node_id"])
assert int(edge["transaction_count"]) == 2
assert float(edge["total_amount"]) == 300.0
assert json.loads(edge["sample_transaction_ids_json"]) == ["TX001"]
assert edge["edge_type"] == "TRANSFERRED_TO"
assert set(["run_id", "node_id", "node_type", "cluster_id", "is_suspicious"]).issubset(nodes.columns)
assert set(["source_node_id", "target_node_id", "edge_type", "total_amount"]).issubset(edges.columns)
```

- [ ] **Step 2: Run graph aggregation test to verify failure**

Run: `.venv/bin/pytest tests/test_graph_builder.py::test_build_graph_artifacts_aggregates_filtered_transfer_edges -q`

Expected: FAIL because `build_graph_artifacts` is still the Phase 4 placeholder.

- [ ] **Step 3: Implement minimal graph builder**

Implement `GraphBuildResult`, artifact schemas, risk/alert loaders, transfer aggregation by source, target, and currency, High/Critical seed selection, one-hop incident edge filtering, Parquet writes, and DuckDB table registration.

- [ ] **Step 4: Run graph aggregation test to verify pass**

Run: `.venv/bin/pytest tests/test_graph_builder.py::test_build_graph_artifacts_aggregates_filtered_transfer_edges -q`

Expected: PASS.

- [ ] **Step 5: Add failing graph limit test**

Add a test with one Critical account and five counterparties. Call:

```python
result = build_graph_artifacts(
    run_dir,
    max_context_accounts=2,
    max_edges=2,
    max_counterparties_per_account=2,
)
```

Assert the Critical account is included, exactly two context account nodes are included, at most two transfer edges are written, and `result.node_count == len(nodes)`.

- [ ] **Step 6: Run graph limit test to verify failure if limits are incomplete**

Run: `.venv/bin/pytest tests/test_graph_builder.py::test_build_graph_artifacts_respects_context_and_edge_limits -q`

Expected: FAIL until all configured limits are enforced.

- [ ] **Step 7: Complete graph limit enforcement**

Rank incident edges deterministically by risk relevance score, total amount, transaction count, source ID, target ID, and currency. Enforce per-account counterparty, context-account, account-node, and edge caps while retaining all retained seed accounts.

- [ ] **Step 8: Run graph builder tests**

Run: `.venv/bin/pytest tests/test_graph_builder.py -q`

Expected: PASS.

## Task 2: Suspicious Cluster Analysis

**Files:**
- Modify: `src/fraud_demo/clusters.py`
- Test: `tests/test_clusters.py`

**Interfaces:**
- Consumes: `graph_nodes.parquet`, `graph_edges.parquet`, `account_risk.parquet`, `alerts.parquet`
- Produces: `ClusterAnalysisResult`
- Produces: `identify_clusters(run_dir: Path | str, *, max_cluster_nodes: int = 100, max_cycle_length: int = 5, max_cycles_per_cluster: int = 20) -> ClusterAnalysisResult`

- [ ] **Step 1: Write failing connected-component cluster test**

Create `tests/test_clusters.py` with bounded account graph fixtures: `ACC_MULE` High, `ACC_A` context, `ACC_B` context, and a separate low-risk edge. Include a transfer cycle among `ACC_MULE`, `ACC_A`, and `ACC_B`. Include `account_risk.parquet` and `alerts.parquet` with null `cluster_id` fields.

Assert:

```python
result = identify_clusters(run_dir)
clusters = pd.read_parquet(result.clusters_path)
nodes = pd.read_parquet(result.graph_nodes_path)
edges = pd.read_parquet(result.graph_edges_path)
risk = pd.read_parquet(run_dir / "account_risk.parquet").set_index("account_id")
alerts = pd.read_parquet(run_dir / "alerts.parquet").set_index("account_id")

cluster = clusters.iloc[0]
assert result.cluster_count == 1
assert cluster["cluster_id"].startswith("CLUSTER_RUN_CLUSTERS_")
assert int(cluster["suspicious_account_count"]) == 1
assert bool(cluster["short_cycle_detected"]) is True
assert risk.loc["ACC_MULE", "cluster_id"] == cluster["cluster_id"]
assert alerts.loc["ACC_MULE", "cluster_id"] == cluster["cluster_id"]
assert "MEMBER_OF_CLUSTER" in set(edges["edge_type"])
assert cluster["cluster_id"] in set(nodes["node_id"])
```

- [ ] **Step 2: Run cluster test to verify failure**

Run: `.venv/bin/pytest tests/test_clusters.py::test_identify_clusters_writes_summaries_and_membership -q`

Expected: FAIL because `identify_clusters` is still the Phase 4 placeholder.

- [ ] **Step 3: Implement minimal clustering**

Implement `ClusterAnalysisResult`, NetworkX graph construction from bounded `TRANSFERRED_TO` edges, connected components containing suspicious accounts, deterministic cluster summaries, cluster node rows, `MEMBER_OF_CLUSTER` edges, `cluster_id` updates for graph nodes, account risk, and alerts, and DuckDB table registration.

- [ ] **Step 4: Run cluster test to verify pass**

Run: `.venv/bin/pytest tests/test_clusters.py::test_identify_clusters_writes_summaries_and_membership -q`

Expected: PASS.

- [ ] **Step 5: Add failing cycle bound test**

Add a test where a component has more nodes than `max_cluster_nodes`. Call `identify_clusters(run_dir, max_cluster_nodes=2)` and assert a cluster row is still emitted but `short_cycle_detected` is false and `short_cycle_account_ids_json` is `[]`.

- [ ] **Step 6: Run cycle bound test to verify failure if needed**

Run: `.venv/bin/pytest tests/test_clusters.py::test_identify_clusters_skips_cycle_detection_when_component_exceeds_limit -q`

Expected: FAIL until cycle detection is skipped for oversized components.

- [ ] **Step 7: Complete bounded cycle enrichment**

Run `networkx.simple_cycles` only for components with node counts less than or equal to `max_cluster_nodes`. Stop after `max_cycles_per_cluster` accepted cycles and keep only cycles with length less than or equal to `max_cycle_length`.

- [ ] **Step 8: Run cluster tests**

Run: `.venv/bin/pytest tests/test_clusters.py -q`

Expected: PASS.

## Task 3: CLI And Manifest Integration

**Files:**
- Modify: `src/fraud_demo/manifests.py`
- Modify: `src/fraud_demo/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `build_graph_artifacts`, `identify_clusters`
- Produces: `build_phase4_manifest(phase3_manifest: dict[str, Any], graph_result: Any, cluster_result: Any, stage_timings_seconds: dict[str, float]) -> dict[str, Any]`
- Produces: a `run` command that completes Phase 4 and writes Phase 4 manifest paths.

- [ ] **Step 1: Write failing CLI test update**

Update `test_run_command_creates_phase3_artifacts` to `test_run_command_creates_phase4_artifacts`. Assert output contains `Phase 4 complete`, graph artifacts exist, manifest status is `phase4_complete`, `phase_status.phase4_graph_clusters == "complete"`, and artifact paths contain `graph_nodes`, `graph_edges`, and `clusters`.

- [ ] **Step 2: Run CLI test to verify failure**

Run: `.venv/bin/pytest tests/test_cli.py::test_run_command_creates_phase4_artifacts -q`

Expected: FAIL because the CLI still stops after Phase 3.

- [ ] **Step 3: Implement CLI and manifest update**

Add `build_phase4_manifest`, import and call graph/clustering stages in `run_pipeline`, time them as `graph_build` and `clustering`, write the Phase 4 manifest, and update the success message.

- [ ] **Step 4: Run CLI tests**

Run: `.venv/bin/pytest tests/test_cli.py -q`

Expected: PASS.

## Task 4: Status, Smoke Run, And Final Verification

**Files:**
- Modify: `IMPLEMENTATION_STATUS.md`

**Interfaces:**
- Consumes all Phase 4 tasks.
- Produces updated implementation status and verification evidence.

- [ ] **Step 1: Run full tests**

Run: `.venv/bin/pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run ruff**

Run: `.venv/bin/ruff check .`

Expected: all checks pass.

- [ ] **Step 3: Run Phase 4 smoke command**

Run: `.venv/bin/python -m fraud_demo generate-data --rows 160 --output /private/tmp/fraud-sentinel-phase4-smoke.csv --seed 42`

Expected: command exits 0 and writes the CSV plus scenario manifest.

Run: `.venv/bin/python -m fraud_demo run --input /private/tmp/fraud-sentinel-phase4-smoke.csv --run-id RUN_PHASE4_SMOKE --artifacts-dir /private/tmp/fraud-sentinel-phase4-artifacts --force`

Expected: command exits 0, prints `Phase 4 complete`, and writes `graph_nodes.parquet`, `graph_edges.parquet`, and `clusters.parquet`.

- [ ] **Step 4: Update implementation status**

Record Phase 4 as complete, list assumptions, verification commands, smoke output, and any non-blocking warnings.

- [ ] **Step 5: Commit and publish**

Run:

```bash
git status --short
git add docs/superpowers/specs/2026-06-22-phase-4-graph-clusters-design.md docs/superpowers/plans/2026-06-22-phase-4-graph-clusters.md src/fraud_demo/graph_builder.py src/fraud_demo/clusters.py src/fraud_demo/manifests.py src/fraud_demo/cli.py tests/test_graph_builder.py tests/test_clusters.py tests/test_cli.py IMPLEMENTATION_STATUS.md
git commit -m "feat: implement phase 4 graph clusters"
git push -u origin codex/phase-4-graph-clusters
```

Expected: branch is pushed and ready for pull request creation and merge.

## Self-Review

- Spec coverage: Tasks cover filtered graph artifacts, transfer aggregation, bounded
  NetworkX clustering, cycle enrichment, cluster IDs on risk and alerts, manifest
  integration, tests, docs, and final verification.
- Placeholder scan: No TBD, TODO, or deferred implementation placeholder remains
  inside Phase 4 scope.
- Type consistency: Function names, dataclass names, artifact names, and manifest keys
  match the design spec.
