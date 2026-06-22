"""Bounded suspicious cluster analysis for Phase 4."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import networkx as nx
import pandas as pd

from fraud_demo.graph_builder import GRAPH_EDGE_COLUMNS, GRAPH_NODE_COLUMNS

CLUSTER_COLUMNS = [
    "run_id",
    "cluster_id",
    "component_id",
    "account_count",
    "suspicious_account_count",
    "high_account_count",
    "critical_account_count",
    "transfer_edge_count",
    "total_transfer_amount",
    "first_seen_at",
    "last_seen_at",
    "max_risk_score",
    "risk_level_counts_json",
    "member_account_ids_json",
    "suspicious_account_ids_json",
    "short_cycle_detected",
    "short_cycle_account_ids_json",
    "created_at",
    "human_review_note",
]

SUSPICIOUS_LEVELS = {"high", "critical"}


@dataclass(frozen=True)
class ClusterAnalysisResult:
    """Artifacts and counts from bounded suspicious cluster analysis."""

    run_id: str
    run_dir: Path
    clusters_path: Path
    graph_nodes_path: Path
    graph_edges_path: Path
    cluster_count: int


def _json_dumps(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _json_value(value: Any) -> object:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _account_nodes(nodes: pd.DataFrame) -> pd.DataFrame:
    return nodes.loc[nodes["node_type"].eq("Account")].copy()


def _transfer_edges(edges: pd.DataFrame) -> pd.DataFrame:
    return edges.loc[edges["edge_type"].eq("TRANSFERRED_TO")].copy()


def _build_component_graph(account_nodes: pd.DataFrame, transfer_edges: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()
    graph.add_nodes_from(str(value) for value in account_nodes["node_id"].tolist())
    for row in transfer_edges.itertuples(index=False):
        graph.add_edge(str(row.source_node_id), str(row.target_node_id))
    return graph


def _risk_level_counts(member_nodes: pd.DataFrame) -> dict[str, int]:
    counts = member_nodes["risk_level"].astype(str).value_counts().to_dict()
    return {str(level): int(count) for level, count in sorted(counts.items())}


def _component_transfer_edges(
    transfer_edges: pd.DataFrame,
    members: set[str],
) -> pd.DataFrame:
    return transfer_edges.loc[
        transfer_edges["source_node_id"].isin(members)
        & transfer_edges["target_node_id"].isin(members)
    ].copy()


def _bounded_cycle_accounts(
    component_edges: pd.DataFrame,
    members: set[str],
    *,
    max_cluster_nodes: int,
    max_cycle_length: int,
    max_cycles_per_cluster: int,
) -> set[str]:
    if len(members) > max_cluster_nodes or component_edges.empty:
        return set()
    graph = nx.DiGraph()
    graph.add_nodes_from(sorted(members))
    for row in component_edges.itertuples(index=False):
        graph.add_edge(str(row.source_node_id), str(row.target_node_id))

    cycle_accounts: set[str] = set()
    accepted_cycles = 0
    for cycle in nx.simple_cycles(graph):
        if len(cycle) <= max_cycle_length:
            cycle_accounts.update(str(account_id) for account_id in cycle)
            accepted_cycles += 1
            if accepted_cycles >= max_cycles_per_cluster:
                break
    return cycle_accounts


def _cluster_candidates(
    run_id: str,
    nodes: pd.DataFrame,
    transfer_edges: pd.DataFrame,
    *,
    max_cluster_nodes: int,
    max_cycle_length: int,
    max_cycles_per_cluster: int,
) -> list[dict[str, object]]:
    account_nodes = _account_nodes(nodes)
    component_graph = _build_component_graph(account_nodes, transfer_edges)
    created_at = datetime.now(UTC).isoformat()
    candidates: list[dict[str, object]] = []

    for members_raw in nx.connected_components(component_graph):
        members = {str(account_id) for account_id in members_raw}
        member_nodes = account_nodes.loc[account_nodes["node_id"].isin(members)].copy()
        suspicious_nodes = member_nodes.loc[
            member_nodes["is_suspicious"].fillna(False).astype(bool)
            | member_nodes["risk_level"].astype(str).str.lower().isin(SUSPICIOUS_LEVELS)
        ]
        if suspicious_nodes.empty:
            continue

        component_edges = _component_transfer_edges(transfer_edges, members)
        cycle_accounts = _bounded_cycle_accounts(
            component_edges,
            members,
            max_cluster_nodes=max_cluster_nodes,
            max_cycle_length=max_cycle_length,
            max_cycles_per_cluster=max_cycles_per_cluster,
        )
        levels = member_nodes["risk_level"].astype(str).str.lower()
        risk_scores = pd.to_numeric(member_nodes["risk_score"], errors="coerce").fillna(0)
        total_amount = float(
            pd.to_numeric(component_edges["total_amount"], errors="coerce").fillna(0).sum()
        )
        first_seen = (
            component_edges["first_seen_at"].dropna().astype(str).min()
            if not component_edges.empty
            else None
        )
        last_seen = (
            component_edges["last_seen_at"].dropna().astype(str).max()
            if not component_edges.empty
            else None
        )
        candidates.append(
            {
                "run_id": run_id,
                "cluster_id": "",
                "component_id": "",
                "account_count": int(len(member_nodes)),
                "suspicious_account_count": int(len(suspicious_nodes)),
                "high_account_count": int(levels.eq("high").sum()),
                "critical_account_count": int(levels.eq("critical").sum()),
                "transfer_edge_count": int(len(component_edges)),
                "total_transfer_amount": total_amount,
                "first_seen_at": first_seen,
                "last_seen_at": last_seen,
                "max_risk_score": int(risk_scores.max()) if not risk_scores.empty else 0,
                "risk_level_counts_json": _json_dumps(_risk_level_counts(member_nodes)),
                "member_account_ids_json": _json_dumps(sorted(members)),
                "suspicious_account_ids_json": _json_dumps(
                    sorted(str(value) for value in suspicious_nodes["node_id"].tolist())
                ),
                "short_cycle_detected": bool(cycle_accounts),
                "short_cycle_account_ids_json": _json_dumps(sorted(cycle_accounts)),
                "created_at": created_at,
                "human_review_note": (
                    "Suspicious connected account cluster requiring human review. "
                    "This output is an investigative aid and does not make an account decision."
                ),
                "_member_accounts": sorted(members),
                "_cycle_accounts": sorted(cycle_accounts),
                "_component_key": "|".join(sorted(members)),
            }
        )

    candidates.sort(
        key=lambda row: (
            -int(row["max_risk_score"]),
            -int(row["suspicious_account_count"]),
            -float(row["total_transfer_amount"]),
            str(row["_component_key"]),
        )
    )
    for index, row in enumerate(candidates, start=1):
        row["cluster_id"] = f"CLUSTER_{run_id}_{index:03d}"
        row["component_id"] = f"COMPONENT_{index:03d}"
    return candidates


def _cluster_node(row: dict[str, object]) -> dict[str, object]:
    cluster_id = str(row["cluster_id"])
    return {
        "run_id": row["run_id"],
        "node_id": cluster_id,
        "node_type": "Cluster",
        "label": cluster_id,
        "account_id": None,
        "cluster_id": cluster_id,
        "risk_score": int(row["max_risk_score"]),
        "risk_level": "Critical" if int(row["critical_account_count"]) else "High",
        "is_suspicious": True,
        "is_context": False,
        "alert_id": None,
        "triggered_rule_ids": [],
        "component_id": row["component_id"],
        "short_cycle_member": False,
        "properties_json": _json_dumps(
            {
                "account_count": row["account_count"],
                "human_review_note": row["human_review_note"],
            }
        ),
    }


def _membership_edge(row: dict[str, object], account_id: str) -> dict[str, object]:
    return {
        "run_id": row["run_id"],
        "source_node_id": account_id,
        "target_node_id": row["cluster_id"],
        "edge_type": "MEMBER_OF_CLUSTER",
        "transaction_count": 0,
        "total_amount": 0.0,
        "currency": None,
        "first_seen_at": None,
        "last_seen_at": None,
        "sample_transaction_ids_json": "[]",
        "risk_relevance_score": float(row["max_risk_score"]),
        "component_id": row["component_id"],
        "properties_json": _json_dumps(
            {
                "review_note": "Account is part of a suspicious cluster requiring human review."
            }
        ),
    }


def _apply_cluster_enrichment(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    candidates: list[dict[str, object]],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str]]:
    enriched_nodes = nodes.loc[~nodes["node_type"].eq("Cluster")].copy()
    enriched_edges = edges.loc[~edges["edge_type"].eq("MEMBER_OF_CLUSTER")].copy()
    account_to_cluster: dict[str, str] = {}
    account_to_component: dict[str, str] = {}
    cycle_accounts: set[str] = set()
    cluster_node_rows: list[dict[str, object]] = []
    membership_rows: list[dict[str, object]] = []

    for row in candidates:
        cluster_node_rows.append(_cluster_node(row))
        for account_id in row["_member_accounts"]:
            account_to_cluster[str(account_id)] = str(row["cluster_id"])
            account_to_component[str(account_id)] = str(row["component_id"])
            membership_rows.append(_membership_edge(row, str(account_id)))
        cycle_accounts.update(str(account_id) for account_id in row["_cycle_accounts"])

    account_mask = enriched_nodes["node_type"].eq("Account")
    for account_id, cluster_id in account_to_cluster.items():
        mask = account_mask & enriched_nodes["node_id"].eq(account_id)
        enriched_nodes.loc[mask, "cluster_id"] = cluster_id
        enriched_nodes.loc[mask, "component_id"] = account_to_component[account_id]
        enriched_nodes.loc[mask, "short_cycle_member"] = account_id in cycle_accounts

    for index, row in enriched_edges.iterrows():
        if row["edge_type"] != "TRANSFERRED_TO":
            continue
        source = str(row["source_node_id"])
        target = str(row["target_node_id"])
        if (
            source in account_to_component
            and account_to_component.get(source) == account_to_component.get(target)
        ):
            enriched_edges.loc[index, "component_id"] = account_to_component[source]

    if cluster_node_rows:
        enriched_nodes = pd.concat(
            [enriched_nodes, pd.DataFrame(cluster_node_rows, columns=GRAPH_NODE_COLUMNS)],
            ignore_index=True,
        )
    if membership_rows:
        enriched_edges = pd.concat(
            [enriched_edges, pd.DataFrame(membership_rows, columns=GRAPH_EDGE_COLUMNS)],
            ignore_index=True,
        )

    cluster_rows = [
        {column: row[column] for column in CLUSTER_COLUMNS}
        for row in candidates
    ]
    clusters = pd.DataFrame(cluster_rows, columns=CLUSTER_COLUMNS)
    return enriched_nodes, enriched_edges, clusters, account_to_cluster


def _update_cluster_ids(path: Path, account_to_cluster: dict[str, str]) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if "cluster_id" not in frame.columns:
        frame["cluster_id"] = None
    if not frame.empty and "account_id" in frame.columns:
        mapped = frame["account_id"].astype(str).map(account_to_cluster)
        frame["cluster_id"] = mapped.combine_first(frame["cluster_id"])
    frame.to_parquet(path, index=False)
    return frame


def _write_cluster_tables(
    run_path: Path,
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    clusters: pd.DataFrame,
    account_risk: pd.DataFrame,
    alerts: pd.DataFrame,
) -> tuple[Path, Path, Path]:
    graph_nodes_path = run_path / "graph_nodes.parquet"
    graph_edges_path = run_path / "graph_edges.parquet"
    clusters_path = run_path / "clusters.parquet"
    nodes.to_parquet(graph_nodes_path, index=False)
    edges.to_parquet(graph_edges_path, index=False)
    clusters.to_parquet(clusters_path, index=False)
    duckdb_path = run_path / "transactions.duckdb"
    with duckdb.connect(str(duckdb_path)) as connection:
        for table_name, frame in [
            ("graph_nodes", nodes),
            ("graph_edges", edges),
            ("clusters", clusters),
            ("account_risk", account_risk),
            ("alerts", alerts),
        ]:
            view_name = f"{table_name}_df"
            connection.register(view_name, frame)
            connection.execute(f"create or replace table {table_name} as select * from {view_name}")
            connection.unregister(view_name)
    return clusters_path, graph_nodes_path, graph_edges_path


def identify_clusters(
    run_dir: Path | str,
    *,
    max_cluster_nodes: int = 100,
    max_cycle_length: int = 5,
    max_cycles_per_cluster: int = 20,
) -> ClusterAnalysisResult:
    """Identify suspicious connected components in the bounded graph artifacts."""

    run_path = Path(run_dir)
    run_id = run_path.name
    nodes = pd.read_parquet(run_path / "graph_nodes.parquet")
    edges = pd.read_parquet(run_path / "graph_edges.parquet")
    transfer_edges = _transfer_edges(edges)
    candidates = _cluster_candidates(
        run_id,
        nodes,
        transfer_edges,
        max_cluster_nodes=max_cluster_nodes,
        max_cycle_length=max_cycle_length,
        max_cycles_per_cluster=max_cycles_per_cluster,
    )
    enriched_nodes, enriched_edges, clusters, account_to_cluster = _apply_cluster_enrichment(
        nodes,
        edges,
        candidates,
    )
    account_risk = _update_cluster_ids(run_path / "account_risk.parquet", account_to_cluster)
    alerts = _update_cluster_ids(run_path / "alerts.parquet", account_to_cluster)
    clusters_path, graph_nodes_path, graph_edges_path = _write_cluster_tables(
        run_path,
        enriched_nodes,
        enriched_edges,
        clusters,
        account_risk,
        alerts,
    )
    return ClusterAnalysisResult(
        run_id=run_id,
        run_dir=run_path,
        clusters_path=clusters_path,
        graph_nodes_path=graph_nodes_path,
        graph_edges_path=graph_edges_path,
        cluster_count=int(len(clusters)),
    )
