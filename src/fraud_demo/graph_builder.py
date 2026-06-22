"""Bounded typed analytical graph construction for Phase 4."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

GRAPH_NODE_COLUMNS = [
    "run_id",
    "node_id",
    "node_type",
    "label",
    "account_id",
    "cluster_id",
    "risk_score",
    "risk_level",
    "is_suspicious",
    "is_context",
    "alert_id",
    "triggered_rule_ids",
    "component_id",
    "short_cycle_member",
    "properties_json",
]

GRAPH_EDGE_COLUMNS = [
    "run_id",
    "source_node_id",
    "target_node_id",
    "edge_type",
    "transaction_count",
    "total_amount",
    "currency",
    "first_seen_at",
    "last_seen_at",
    "sample_transaction_ids_json",
    "risk_relevance_score",
    "component_id",
    "properties_json",
]

SUSPICIOUS_LEVELS = {"high", "critical"}


@dataclass(frozen=True)
class GraphBuildResult:
    """Artifacts and counts from filtered graph construction."""

    run_id: str
    run_dir: Path
    graph_nodes_path: Path
    graph_edges_path: Path
    node_count: int
    edge_count: int
    suspicious_account_count: int


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


def _json_dumps(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if isinstance(value, str):
        if not value:
            return []
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        if isinstance(loaded, list):
            return [str(item) for item in loaded]
        return [str(loaded)]
    if hasattr(value, "tolist"):
        return [str(item) for item in value.tolist()]
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass
    return [str(value)]


def _read_transactions(run_path: Path) -> pd.DataFrame:
    transactions = pd.read_parquet(run_path / "normalized_transactions.parquet")
    if transactions.empty:
        return transactions
    transactions = transactions.copy()
    transactions["event_timestamp"] = pd.to_datetime(
        transactions["event_timestamp"],
        utc=True,
    )
    transactions["amount"] = pd.to_numeric(transactions["amount"], errors="coerce").fillna(0.0)
    for column in ["sender_account_id", "receiver_account_id", "currency"]:
        transactions[column] = transactions[column].astype(str)
    return transactions


def _read_alerts(run_path: Path) -> pd.DataFrame:
    alerts_path = run_path / "alerts.parquet"
    if not alerts_path.exists():
        return pd.DataFrame(columns=["account_id", "alert_id"])
    return pd.read_parquet(alerts_path)


def _suspicious_accounts(risk: pd.DataFrame, max_account_nodes: int) -> list[str]:
    if risk.empty:
        return []
    candidates = risk.loc[
        risk["risk_level"].astype(str).str.lower().isin(SUSPICIOUS_LEVELS)
    ].copy()
    if candidates.empty:
        return []
    candidates["risk_score"] = pd.to_numeric(
        candidates["risk_score"],
        errors="coerce",
    ).fillna(0)
    candidates = candidates.sort_values(
        ["risk_score", "account_id"],
        ascending=[False, True],
        kind="mergesort",
    )
    return [str(value) for value in candidates["account_id"].head(max_account_nodes).tolist()]


def _risk_maps(risk: pd.DataFrame) -> tuple[dict[str, pd.Series], dict[str, float]]:
    rows = {str(row["account_id"]): row for _, row in risk.iterrows()}
    scores = {
        account_id: float(pd.to_numeric(row.get("risk_score"), errors="coerce") or 0.0)
        for account_id, row in rows.items()
    }
    return rows, scores


def _aggregate_transfers(
    transactions: pd.DataFrame,
    *,
    max_sample_transactions: int,
) -> pd.DataFrame:
    if transactions.empty:
        return pd.DataFrame(
            columns=[
                "source_node_id",
                "target_node_id",
                "currency",
                "transaction_count",
                "total_amount",
                "first_seen_at",
                "last_seen_at",
                "sample_transaction_ids_json",
            ]
        )

    records: list[dict[str, object]] = []
    grouped = transactions.groupby(
        ["sender_account_id", "receiver_account_id", "currency"],
        dropna=False,
        sort=True,
    )
    for (source, target, currency), group in grouped:
        ordered_ids = sorted(str(value) for value in group["transaction_id"].dropna().tolist())
        records.append(
            {
                "source_node_id": str(source),
                "target_node_id": str(target),
                "currency": str(currency),
                "transaction_count": int(len(group)),
                "total_amount": float(group["amount"].sum()),
                "first_seen_at": _json_value(group["event_timestamp"].min()),
                "last_seen_at": _json_value(group["event_timestamp"].max()),
                "sample_transaction_ids_json": _json_dumps(
                    ordered_ids[:max_sample_transactions]
                ),
            }
        )
    return pd.DataFrame(records)


def _score_edges(
    edges: pd.DataFrame,
    *,
    suspicious_accounts: set[str],
    risk_scores: dict[str, float],
) -> pd.DataFrame:
    if edges.empty:
        edges["risk_relevance_score"] = []
        return edges
    scored = edges.copy()
    scores: list[float] = []
    for row in scored.itertuples(index=False):
        source = str(row.source_node_id)
        target = str(row.target_node_id)
        endpoint_bonus = (
            100.0
            if source in suspicious_accounts or target in suspicious_accounts
            else 0.0
        )
        scores.append(
            endpoint_bonus
            + risk_scores.get(source, 0.0)
            + risk_scores.get(target, 0.0)
            + min(float(row.total_amount) / 1_000_000, 1.0)
        )
    scored["risk_relevance_score"] = scores
    return scored


def _sort_edges(edges: pd.DataFrame) -> pd.DataFrame:
    if edges.empty:
        return edges
    return edges.sort_values(
        [
            "risk_relevance_score",
            "total_amount",
            "transaction_count",
            "source_node_id",
            "target_node_id",
            "currency",
        ],
        ascending=[False, False, False, True, True, True],
        kind="mergesort",
    )


def _select_incident_edges(
    edges: pd.DataFrame,
    suspicious_accounts: list[str],
    *,
    max_counterparties_per_account: int,
) -> pd.DataFrame:
    if edges.empty or not suspicious_accounts:
        return edges.head(0).copy()
    selected_indexes: set[int] = set()
    sorted_edges = _sort_edges(edges)
    for account_id in suspicious_accounts:
        for direction_mask in [
            sorted_edges["target_node_id"].eq(account_id),
            sorted_edges["source_node_id"].eq(account_id),
        ]:
            incident = sorted_edges.loc[direction_mask]
            counterparties_seen: set[str] = set()
            for index, row in incident.iterrows():
                counterparty = (
                    str(row["source_node_id"])
                    if row["target_node_id"] == account_id
                    else str(row["target_node_id"])
                )
                if counterparty in counterparties_seen:
                    continue
                selected_indexes.add(int(index))
                counterparties_seen.add(counterparty)
                if len(counterparties_seen) >= max_counterparties_per_account:
                    break
    return _sort_edges(edges.loc[sorted(selected_indexes)].copy())


def _context_accounts(
    selected_edges: pd.DataFrame,
    suspicious_accounts: set[str],
    *,
    max_context_accounts: int,
) -> list[str]:
    if selected_edges.empty:
        return []
    strengths: dict[str, tuple[float, float, int]] = {}
    for row in selected_edges.itertuples(index=False):
        for account_id in [str(row.source_node_id), str(row.target_node_id)]:
            if account_id in suspicious_accounts:
                continue
            current = strengths.get(account_id, (0.0, 0.0, 0))
            candidate = (
                float(row.risk_relevance_score),
                float(row.total_amount),
                int(row.transaction_count),
            )
            if candidate > current:
                strengths[account_id] = candidate
    return [
        account_id
        for account_id, _strength in sorted(
            strengths.items(),
            key=lambda item: (-item[1][0], -item[1][1], -item[1][2], item[0]),
        )[:max_context_accounts]
    ]


def _alert_map(alerts: pd.DataFrame) -> dict[str, str | None]:
    if alerts.empty or "account_id" not in alerts or "alert_id" not in alerts:
        return {}
    return {
        str(row["account_id"]): str(row["alert_id"])
        for _, row in alerts.dropna(subset=["account_id", "alert_id"]).iterrows()
    }


def _node_record(
    run_id: str,
    account_id: str,
    *,
    risk_row: pd.Series | None,
    is_suspicious: bool,
    alert_id: str | None,
) -> dict[str, object]:
    risk_score = 0
    risk_level = "Context"
    triggered_rule_ids: list[str] = []
    if risk_row is not None:
        risk_score = int(pd.to_numeric(risk_row.get("risk_score"), errors="coerce") or 0)
        risk_level = str(risk_row.get("risk_level") or risk_level)
        triggered_rule_ids = _as_list(risk_row.get("triggered_rule_ids"))
    return {
        "run_id": run_id,
        "node_id": account_id,
        "node_type": "Account",
        "label": account_id,
        "account_id": account_id,
        "cluster_id": None,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "is_suspicious": bool(is_suspicious),
        "is_context": not is_suspicious,
        "alert_id": alert_id,
        "triggered_rule_ids": triggered_rule_ids,
        "component_id": None,
        "short_cycle_member": False,
        "properties_json": _json_dumps(
            {
                "review_note": (
                    "Suspicious indicator requiring human review."
                    if is_suspicious
                    else "One-hop graph context for a suspicious account."
                )
            }
        ),
    }


def _build_nodes(
    run_id: str,
    account_ids: list[str],
    *,
    suspicious_accounts: set[str],
    risk_rows: dict[str, pd.Series],
    alerts: pd.DataFrame,
) -> pd.DataFrame:
    alert_ids = _alert_map(alerts)
    records = [
        _node_record(
            run_id,
            account_id,
            risk_row=risk_rows.get(account_id),
            is_suspicious=account_id in suspicious_accounts,
            alert_id=alert_ids.get(account_id),
        )
        for account_id in account_ids
    ]
    return pd.DataFrame(records, columns=GRAPH_NODE_COLUMNS)


def _edge_records(run_id: str, selected_edges: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for row in selected_edges.itertuples(index=False):
        records.append(
            {
                "run_id": run_id,
                "source_node_id": str(row.source_node_id),
                "target_node_id": str(row.target_node_id),
                "edge_type": "TRANSFERRED_TO",
                "transaction_count": int(row.transaction_count),
                "total_amount": float(row.total_amount),
                "currency": str(row.currency),
                "first_seen_at": row.first_seen_at,
                "last_seen_at": row.last_seen_at,
                "sample_transaction_ids_json": str(row.sample_transaction_ids_json),
                "risk_relevance_score": float(row.risk_relevance_score),
                "component_id": None,
                "properties_json": _json_dumps(
                    {
                        "review_note": (
                            "Aggregated account-to-account transfer edge for "
                            "human review."
                        )
                    }
                ),
            }
        )
    return pd.DataFrame(records, columns=GRAPH_EDGE_COLUMNS)


def _write_graph_tables(
    run_path: Path,
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
) -> tuple[Path, Path]:
    graph_nodes_path = run_path / "graph_nodes.parquet"
    graph_edges_path = run_path / "graph_edges.parquet"
    nodes.to_parquet(graph_nodes_path, index=False)
    edges.to_parquet(graph_edges_path, index=False)
    duckdb_path = run_path / "transactions.duckdb"
    with duckdb.connect(str(duckdb_path)) as connection:
        connection.register("graph_nodes_df", nodes)
        connection.register("graph_edges_df", edges)
        connection.execute("create or replace table graph_nodes as select * from graph_nodes_df")
        connection.execute("create or replace table graph_edges as select * from graph_edges_df")
        connection.unregister("graph_nodes_df")
        connection.unregister("graph_edges_df")
    return graph_nodes_path, graph_edges_path


def build_graph_artifacts(
    run_dir: Path | str,
    *,
    max_account_nodes: int = 500,
    max_context_accounts: int = 500,
    max_edges: int = 5_000,
    max_counterparties_per_account: int = 30,
    max_sample_transactions: int = 5,
) -> GraphBuildResult:
    """Build bounded account graph nodes and aggregated transfer edges for a run."""

    run_path = Path(run_dir)
    run_id = run_path.name
    transactions = _read_transactions(run_path)
    risk = pd.read_parquet(run_path / "account_risk.parquet")
    alerts = _read_alerts(run_path)
    risk_rows, risk_scores = _risk_maps(risk)
    seed_accounts = _suspicious_accounts(risk, max_account_nodes)
    seed_set = set(seed_accounts)

    aggregated = _aggregate_transfers(
        transactions,
        max_sample_transactions=max_sample_transactions,
    )
    scored = _score_edges(
        aggregated,
        suspicious_accounts=seed_set,
        risk_scores=risk_scores,
    )
    selected = _select_incident_edges(
        scored,
        seed_accounts,
        max_counterparties_per_account=max_counterparties_per_account,
    )
    context_accounts = _context_accounts(
        selected,
        seed_set,
        max_context_accounts=max_context_accounts,
    )

    remaining_slots = max(max_account_nodes - len(seed_accounts), 0)
    account_ids = [*seed_accounts, *context_accounts[:remaining_slots]]
    selected = selected.loc[
        selected["source_node_id"].isin(account_ids)
        & selected["target_node_id"].isin(account_ids)
    ]
    selected = _sort_edges(selected).head(max_edges).reset_index(drop=True)

    nodes = _build_nodes(
        run_id,
        account_ids,
        suspicious_accounts=seed_set,
        risk_rows=risk_rows,
        alerts=alerts,
    )
    edges = _edge_records(run_id, selected)
    graph_nodes_path, graph_edges_path = _write_graph_tables(run_path, nodes, edges)

    return GraphBuildResult(
        run_id=run_id,
        run_dir=run_path,
        graph_nodes_path=graph_nodes_path,
        graph_edges_path=graph_edges_path,
        node_count=int(len(nodes)),
        edge_count=int(len(edges)),
        suspicious_account_count=int(len(seed_accounts)),
    )
