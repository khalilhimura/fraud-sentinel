# Phase 4 Graph And Clusters Design

## Summary

Phase 4 adds bounded typed graph artifacts and deterministic suspicious-cluster
summaries to the Phase 3 pipeline. It consumes `normalized_transactions.parquet`,
`account_risk.parquet`, and `alerts.parquet`, then writes:

- `graph_nodes.parquet`
- `graph_edges.parquet`
- `clusters.parquet`

The outputs are suspicious indicators requiring human review. They do not label any
account or cluster as confirmed fraud, and they do not generate OKF Markdown files.

## Requirements

- Follow `PRD.md` Phase 4, FR-012, and FR-013.
- Preserve Phase 1 through Phase 3 behavior and artifacts.
- Use NetworkX only on filtered and bounded suspicious graphs.
- Produce bounded `graph_nodes.parquet`, `graph_edges.parquet`, and
  `clusters.parquet` artifacts.
- Include all High and Critical accounts, relevant one-hop counterparties, and
  bounded top transfer edges.
- Aggregate account-to-account `TRANSFERRED_TO` edges from
  `normalized_transactions.parquet`.
- Add `MEMBER_OF_CLUSTER` graph edges and `cluster_id` fields for clustered accounts.
- Update `account_risk.parquet` and `alerts.parquet` `cluster_id` values after
  clustering.
- Register graph, cluster, updated account risk, and updated alert tables in the run
  DuckDB database.
- Update the run manifest with `graph_build` and `clustering` timings, graph artifact
  paths, `cluster_count`, and Phase 4 completion.
- Keep graph rendering and algorithm payloads bounded by configuration defaults.
- Do not create Markdown or OKF files in Phase 4.

## Design Options

### Option A: Pipeline-owned filtered graph

Build graph artifacts directly from Phase 3 run artifacts. Filter to High/Critical
accounts, add bounded one-hop transfer context, then run NetworkX connected-component
and cycle analysis only on the resulting graph.

Trade-offs: This directly matches the PRD, protects demo performance, and creates a
stable downstream contract for OKF and dashboard phases. It does not compute global
graph centrality over every account.

### Option B: Full transfer aggregation then filter in NetworkX

Aggregate every account-to-account transfer, load the full graph into NetworkX, then
filter the graph for suspicious accounts.

Trade-offs: This is simpler conceptually but violates the PRD requirement to avoid
running graph algorithms on the full raw graph.

### Option C: DuckDB-only components

Use SQL for edge aggregation and iterative component labeling, avoiding NetworkX.

Trade-offs: This can be optimized later, but it adds complexity and does not use the
recommended MVP graph-analysis stack.

## Decision

Use Option A. Phase 4 will create a filtered analytical graph first, then run NetworkX
only against that bounded graph. This keeps the MVP deterministic, explainable, and
safe for local demo runs while preserving room for Phase 8 performance tuning.

## Public Interfaces

`src/fraud_demo/graph_builder.py` will expose:

```python
@dataclass(frozen=True)
class GraphBuildResult:
    run_id: str
    run_dir: Path
    graph_nodes_path: Path
    graph_edges_path: Path
    node_count: int
    edge_count: int
    suspicious_account_count: int

def build_graph_artifacts(
    run_dir: Path | str,
    *,
    max_account_nodes: int = 500,
    max_context_accounts: int = 500,
    max_edges: int = 5_000,
    max_counterparties_per_account: int = 30,
    max_sample_transactions: int = 5,
) -> GraphBuildResult:
    ...
```

`src/fraud_demo/clusters.py` will expose:

```python
@dataclass(frozen=True)
class ClusterAnalysisResult:
    run_id: str
    run_dir: Path
    clusters_path: Path
    graph_nodes_path: Path
    graph_edges_path: Path
    cluster_count: int

def identify_clusters(
    run_dir: Path | str,
    *,
    max_cluster_nodes: int = 100,
    max_cycle_length: int = 5,
    max_cycles_per_cluster: int = 20,
) -> ClusterAnalysisResult:
    ...
```

`src/fraud_demo/manifests.py` will add:

```python
def build_phase4_manifest(
    phase3_manifest: dict[str, Any],
    graph_result: Any,
    cluster_result: Any,
    stage_timings_seconds: dict[str, float],
) -> dict[str, Any]:
    ...
```

The CLI `run` command will call feature engineering, scoring, initial alert
generation, graph build, clustering, and final manifest writing in order.

## Filtering Contract

High and Critical accounts are the suspicious seed set. The graph builder must include
every seed account even when it has no selected transfer edge. It then aggregates all
account-to-account transfers by sender, receiver, and currency, computes edge
relevance, and selects bounded one-hop transfer context:

1. Incident edges touching each seed account are ranked by relevance, total amount,
   transaction count, and account IDs.
2. At most `max_counterparties_per_account` inbound and outbound counterparties are
   selected per seed account.
3. Context accounts are sorted by strongest selected incident edge and capped at
   `max_context_accounts`.
4. Transfer edges are limited to selected account pairs and capped at `max_edges`.
5. Account nodes are capped at `max_account_nodes`, but seed accounts are never
   dropped unless there are more seeds than the cap. If that happens, the highest-risk
   seeds are retained and the manifest/status notes should record the configured cap.

This filtered graph is the only graph passed to NetworkX.

## Graph Node Schema

`graph_nodes.parquet` contains account nodes after graph build and cluster nodes after
cluster enrichment. Required fields:

- `run_id`
- `node_id`
- `node_type`
- `label`
- `account_id`
- `cluster_id`
- `risk_score`
- `risk_level`
- `is_suspicious`
- `is_context`
- `alert_id`
- `triggered_rule_ids`
- `component_id`
- `short_cycle_member`
- `properties_json`

Account `node_id` values are account IDs. Cluster `node_id` values are cluster IDs.
`properties_json` may contain bounded helper fields for dashboard and OKF phases, but
must not contain raw transaction descriptions.

## Graph Edge Schema

`graph_edges.parquet` contains `TRANSFERRED_TO` edges after graph build and
`MEMBER_OF_CLUSTER` edges after cluster enrichment. Required fields:

- `run_id`
- `source_node_id`
- `target_node_id`
- `edge_type`
- `transaction_count`
- `total_amount`
- `currency`
- `first_seen_at`
- `last_seen_at`
- `sample_transaction_ids_json`
- `risk_relevance_score`
- `component_id`
- `properties_json`

Transfer edges are aggregated by source account, target account, and currency.
`sample_transaction_ids_json` stores at most `max_sample_transactions` sorted
transaction IDs. `MEMBER_OF_CLUSTER` edges use zero counts and amounts, null currency
and timestamps, and properties that state the relationship requires human review.

## Cluster Schema

`clusters.parquet` contains one row per connected component that includes at least one
High or Critical account. Required fields:

- `run_id`
- `cluster_id`
- `component_id`
- `account_count`
- `suspicious_account_count`
- `high_account_count`
- `critical_account_count`
- `transfer_edge_count`
- `total_transfer_amount`
- `first_seen_at`
- `last_seen_at`
- `max_risk_score`
- `risk_level_counts_json`
- `member_account_ids_json`
- `suspicious_account_ids_json`
- `short_cycle_detected`
- `short_cycle_account_ids_json`
- `created_at`
- `human_review_note`

Cluster IDs are deterministic for a run: `CLUSTER_<run_id>_<NNN>`, sorted by maximum
risk score, suspicious account count, total amount, and component ID.

## Cluster Enrichment

`identify_clusters` loads only `graph_nodes.parquet` and `graph_edges.parquet`.
It builds an undirected NetworkX graph from bounded `TRANSFERRED_TO` account edges to
find connected components. It then builds a directed bounded subgraph per component
only when the component has at most `max_cluster_nodes` nodes, using
`networkx.simple_cycles` to mark cycles up to `max_cycle_length` and at most
`max_cycles_per_cluster` cycles.

The cluster stage rewrites:

- `clusters.parquet`
- `graph_nodes.parquet` with `cluster_id`, `component_id`, and `short_cycle_member`
- `graph_edges.parquet` with component IDs plus `MEMBER_OF_CLUSTER` rows
- `account_risk.parquet` with `cluster_id` for accounts in clusters
- `alerts.parquet` with `cluster_id` for alert accounts in clusters

## Manifest Updates

The run manifest status becomes `phase4_complete`. It records:

- `artifact_paths.graph_nodes`
- `artifact_paths.graph_edges`
- `artifact_paths.clusters`
- `cluster_count`
- `stage_timings_seconds.graph_build`
- `stage_timings_seconds.clustering`
- `phase_status.phase4_graph_clusters = complete`

Phase 4 preserves Phase 3 counts and paths, including alert count and rules config
hash.

## Testing

The TDD suite will add:

- `tests/test_graph_builder.py` for transfer edge aggregation, filtered node and edge
  selection, schemas, sample transaction limits, bounded context limits, and DuckDB
  registration.
- `tests/test_clusters.py` for connected components, deterministic cluster summaries,
  bounded cycle enrichment, `MEMBER_OF_CLUSTER` edges, `cluster_id` updates on risk and
  alerts, and DuckDB registration.
- CLI coverage updates verifying `run` writes Phase 4 artifacts and manifest status.

Verification will include:

- `.venv/bin/pytest -q`
- `.venv/bin/ruff check .`
- A smoke run using generated synthetic data.

## Self Review

- Placeholder scan: No TBD, TODO, or deferred Phase 4 implementation placeholders
  remain.
- Consistency check: Public interfaces, artifact names, schema fields, and manifest
  updates match the PRD and the Phase 3 run directory layout.
- Scope check: Phase 4 is limited to graph artifacts, clustering, bounded cycle
  enrichment, cluster ID propagation, DuckDB registration, manifest updates, tests, and
  status docs. OKF Markdown export remains Phase 5.
- Ambiguity resolution: Cluster IDs are propagated to `account_risk` and `alerts`
  because that is the cleanest downstream contract for dashboard and OKF consumers.
