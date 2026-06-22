import json
from pathlib import Path

import duckdb
import pandas as pd

from fraud_demo.clusters import identify_clusters


def _node(
    account_id: str,
    risk_score: int,
    risk_level: str,
    *,
    is_suspicious: bool = False,
) -> dict[str, object]:
    return {
        "run_id": "RUN_CLUSTERS",
        "node_id": account_id,
        "node_type": "Account",
        "label": account_id,
        "account_id": account_id,
        "cluster_id": None,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "is_suspicious": is_suspicious,
        "is_context": not is_suspicious,
        "alert_id": f"ALERT_RUN_CLUSTERS_{account_id}" if is_suspicious else None,
        "triggered_rule_ids": ["high_fan_in"] if is_suspicious else [],
        "component_id": None,
        "short_cycle_member": False,
        "properties_json": "{}",
    }


def _transfer(source: str, target: str, amount: float) -> dict[str, object]:
    return {
        "run_id": "RUN_CLUSTERS",
        "source_node_id": source,
        "target_node_id": target,
        "edge_type": "TRANSFERRED_TO",
        "transaction_count": 1,
        "total_amount": amount,
        "currency": "MYR",
        "first_seen_at": "2026-01-08T08:00:00+00:00",
        "last_seen_at": "2026-01-08T08:05:00+00:00",
        "sample_transaction_ids_json": json.dumps([f"TX_{source}_{target}"]),
        "risk_relevance_score": amount,
        "component_id": None,
        "properties_json": "{}",
    }


def _write_cluster_inputs(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            _node("ACC_MULE", 60, "High", is_suspicious=True),
            _node("ACC_A", 0, "Low"),
            _node("ACC_B", 0, "Low"),
            _node("ACC_LOW_1", 0, "Low"),
            _node("ACC_LOW_2", 0, "Low"),
        ]
    ).to_parquet(run_dir / "graph_nodes.parquet", index=False)
    pd.DataFrame(
        [
            _transfer("ACC_A", "ACC_MULE", 100.0),
            _transfer("ACC_MULE", "ACC_B", 90.0),
            _transfer("ACC_B", "ACC_A", 80.0),
            _transfer("ACC_LOW_1", "ACC_LOW_2", 500.0),
        ]
    ).to_parquet(run_dir / "graph_edges.parquet", index=False)
    pd.DataFrame(
        [
            {
                "run_id": "RUN_CLUSTERS",
                "account_id": "ACC_MULE",
                "risk_score": 60,
                "risk_level": "High",
                "cluster_id": None,
            },
            {
                "run_id": "RUN_CLUSTERS",
                "account_id": "ACC_A",
                "risk_score": 0,
                "risk_level": "Low",
                "cluster_id": None,
            },
            {
                "run_id": "RUN_CLUSTERS",
                "account_id": "ACC_B",
                "risk_score": 0,
                "risk_level": "Low",
                "cluster_id": None,
            },
        ]
    ).to_parquet(run_dir / "account_risk.parquet", index=False)
    pd.DataFrame(
        [
            {
                "run_id": "RUN_CLUSTERS",
                "account_id": "ACC_MULE",
                "alert_id": "ALERT_RUN_CLUSTERS_ACC_MULE",
                "cluster_id": None,
            }
        ]
    ).to_parquet(run_dir / "alerts.parquet", index=False)


def test_identify_clusters_writes_summaries_and_membership(tmp_path: Path):
    run_dir = tmp_path / "artifacts" / "runs" / "RUN_CLUSTERS"
    _write_cluster_inputs(run_dir)

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
    with duckdb.connect(str(run_dir / "transactions.duckdb"), read_only=True) as connection:
        assert connection.execute("select count(*) from clusters").fetchone()[0] == 1


def test_identify_clusters_skips_cycle_detection_when_component_exceeds_limit(tmp_path: Path):
    run_dir = tmp_path / "artifacts" / "runs" / "RUN_CLUSTERS"
    _write_cluster_inputs(run_dir)

    result = identify_clusters(run_dir, max_cluster_nodes=2)

    clusters = pd.read_parquet(result.clusters_path)
    cluster = clusters.iloc[0]
    assert result.cluster_count == 1
    assert bool(cluster["short_cycle_detected"]) is False
    assert json.loads(cluster["short_cycle_account_ids_json"]) == []
