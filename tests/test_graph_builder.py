import json
from pathlib import Path

import duckdb
import pandas as pd

from fraud_demo.graph_builder import build_graph_artifacts


def _transaction(
    transaction_id: str,
    timestamp: str,
    sender: str,
    receiver: str,
    amount: float,
) -> dict[str, object]:
    return {
        "transaction_id": transaction_id,
        "event_timestamp": timestamp,
        "sender_account_id": sender,
        "receiver_account_id": receiver,
        "amount": amount,
        "currency": "MYR",
    }


def _risk_row(
    account_id: str,
    risk_score: int,
    risk_level: str,
    *,
    triggered_rule_ids: list[str] | None = None,
) -> dict[str, object]:
    return {
        "run_id": "RUN_GRAPH",
        "account_id": account_id,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "triggered_rule_ids": triggered_rule_ids or [],
        "triggered_rule_count": len(triggered_rule_ids or []),
        "cluster_id": None,
    }


def _write_graph_inputs(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    transactions = pd.DataFrame(
        [
            _transaction("TX001", "2026-01-08T08:00:00Z", "ACC_A", "ACC_MULE", 100.0),
            _transaction("TX002", "2026-01-08T08:05:00Z", "ACC_A", "ACC_MULE", 200.0),
            _transaction("TX003", "2026-01-08T09:00:00Z", "ACC_MULE", "ACC_OUT", 250.0),
            _transaction("TX004", "2026-01-08T10:00:00Z", "ACC_LOW_1", "ACC_LOW_2", 999.0),
        ]
    )
    transactions["event_timestamp"] = pd.to_datetime(transactions["event_timestamp"], utc=True)
    transactions.to_parquet(run_dir / "normalized_transactions.parquet", index=False)
    pd.DataFrame(
        [
            _risk_row("ACC_MULE", 60, "High", triggered_rule_ids=["high_fan_in"]),
            _risk_row("ACC_A", 0, "Low"),
            _risk_row("ACC_OUT", 0, "Low"),
            _risk_row("ACC_LOW_1", 0, "Low"),
            _risk_row("ACC_LOW_2", 0, "Low"),
        ]
    ).to_parquet(run_dir / "account_risk.parquet", index=False)
    pd.DataFrame(
        [
            {
                "run_id": "RUN_GRAPH",
                "account_id": "ACC_MULE",
                "alert_id": "ALERT_RUN_GRAPH_ACC_MULE",
                "cluster_id": None,
            }
        ]
    ).to_parquet(run_dir / "alerts.parquet", index=False)


def test_build_graph_artifacts_aggregates_filtered_transfer_edges(tmp_path: Path):
    run_dir = tmp_path / "artifacts" / "runs" / "RUN_GRAPH"
    _write_graph_inputs(run_dir)

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
    assert {
        "run_id",
        "node_id",
        "node_type",
        "cluster_id",
        "is_suspicious",
    }.issubset(nodes.columns)
    assert {
        "source_node_id",
        "target_node_id",
        "edge_type",
        "total_amount",
    }.issubset(edges.columns)
    with duckdb.connect(str(run_dir / "transactions.duckdb"), read_only=True) as connection:
        assert connection.execute("select count(*) from graph_nodes").fetchone()[0] == len(nodes)
        assert connection.execute("select count(*) from graph_edges").fetchone()[0] == len(edges)


def test_build_graph_artifacts_respects_context_and_edge_limits(tmp_path: Path):
    run_dir = tmp_path / "artifacts" / "runs" / "RUN_GRAPH_LIMITS"
    run_dir.mkdir(parents=True, exist_ok=True)
    transactions = pd.DataFrame(
        [
            _transaction(
                f"TX_LIMIT_{index}",
                f"2026-01-08T08:0{index}:00Z",
                f"ACC_CP_{index}",
                "ACC_CORE",
                1_000.0 + index,
            )
            for index in range(5)
        ]
    )
    transactions["event_timestamp"] = pd.to_datetime(transactions["event_timestamp"], utc=True)
    transactions.to_parquet(run_dir / "normalized_transactions.parquet", index=False)
    risk_rows = [
        {
            **_risk_row("ACC_CORE", 85, "Critical", triggered_rule_ids=["short_cycle"]),
            "run_id": "RUN_GRAPH_LIMITS",
        }
    ]
    risk_rows.extend(
        {
            **_risk_row(f"ACC_CP_{index}", 0, "Low"),
            "run_id": "RUN_GRAPH_LIMITS",
        }
        for index in range(5)
    )
    pd.DataFrame(risk_rows).to_parquet(run_dir / "account_risk.parquet", index=False)
    pd.DataFrame(columns=["run_id", "account_id", "alert_id", "cluster_id"]).to_parquet(
        run_dir / "alerts.parquet",
        index=False,
    )

    result = build_graph_artifacts(
        run_dir,
        max_context_accounts=2,
        max_edges=2,
        max_counterparties_per_account=2,
    )

    nodes = pd.read_parquet(result.graph_nodes_path)
    edges = pd.read_parquet(result.graph_edges_path)
    assert "ACC_CORE" in set(nodes["node_id"])
    assert len(nodes.loc[nodes["is_context"]]) == 2
    assert len(edges.loc[edges["edge_type"].eq("TRANSFERRED_TO")]) <= 2
    assert result.node_count == len(nodes)
