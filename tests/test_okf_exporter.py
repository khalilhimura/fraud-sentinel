import json
from pathlib import Path

import duckdb
import pandas as pd

from fraud_demo.okf_exporter import export_okf_bundle


def _write_okf_config(tmp_path: Path, *, limits: dict[str, int] | None = None) -> Path:
    bundle_path = tmp_path / "okf_bundle"
    export_limits = {
        "max_accounts": 500,
        "max_alerts": 500,
        "max_clusters": 100,
        "max_devices": 200,
        "max_ips": 200,
        "max_counterparties_per_account": 30,
        "max_sample_transactions_per_alert": 20,
    }
    if limits:
        export_limits.update(limits)
    lines = [
        'version: "0.1"',
        "bundle_name: Mule Account Fraud Knowledge Graph",
        f"output_dir: {bundle_path}",
        "link_style: relative",
        "include_root_version_frontmatter: true",
        "generate_index_files: true",
        "generate_log_files: true",
        "include_typed_relations_extension: true",
        "export_limits:",
    ]
    lines.extend(f"  {key}: {value}" for key, value in export_limits.items())
    lines.extend(
        [
            "privacy:",
            "  pseudonymize_account_ids: false",
            "  pseudonymize_device_ids: true",
            "  pseudonymize_ip_addresses: true",
            "  include_transaction_descriptions: false",
            "  include_customer_pii: false",
            "concept_types:",
            "  account: Fraud Account",
            "  alert: Fraud Alert",
            "  cluster: Fraud Cluster",
            "  signal: Fraud Signal",
            "  device: Fraud Device",
            "  ip: Fraud IP Address",
            "  metric: Fraud Metric",
            "  run: Fraud Pipeline Run",
            "  dataset: Fraud Dataset",
            "  runbook: Fraud Runbook",
        ]
    )
    config_path = tmp_path / "okf.yaml"
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config_path


def _write_run_artifacts(tmp_path: Path, *, reserved_accounts: bool = False) -> Path:
    run_dir = tmp_path / "artifacts" / "runs" / "RUN_OKF"
    run_dir.mkdir(parents=True)

    if reserved_accounts:
        account_ids = ["index", "log", "ACC_MULE"]
    else:
        account_ids = ["ACC_MULE", "ACC_CONTEXT"]

    risk_rows = []
    for index, account_id in enumerate(account_ids):
        risk_rows.append(
            {
                "run_id": "RUN_OKF",
                "account_id": account_id,
                "snapshot_timestamp": "2026-01-01T00:00:00+00:00",
                "raw_score": 80 - index,
                "risk_score": 80 - index,
                "risk_level": "Critical" if index == 0 else "High",
                "triggered_rule_ids": ["rapid_pass_through"],
                "triggered_rule_count": 1,
                "not_evaluated_rule_ids": [],
                "rules_config_hash": "ruleshash",
                "created_at": "2026-01-01T00:02:00+00:00",
                "first_activity_at": "2026-01-01T00:00:00+00:00",
                "last_activity_at": "2026-01-01T00:01:00+00:00",
                "incoming_amount_7d": 5000.0,
                "outgoing_amount_7d": 4900.0,
                "unique_senders_7d": 12,
                "unique_receivers_7d": 3,
                "hold_time_proxy_minutes": 15.0,
                "source_data_fingerprint": "sourcehash",
                "cluster_id": "CLUSTER_RUN_OKF_001",
            }
        )
    account_risk = pd.DataFrame(risk_rows)
    account_risk.to_parquet(run_dir / "account_risk.parquet", index=False)

    alert_account = account_ids[0]
    alerts = pd.DataFrame(
        [
            {
                "alert_id": f"ALERT_RUN_OKF_{alert_account}",
                "run_id": "RUN_OKF",
                "account_id": alert_account,
                "risk_score": 80,
                "risk_level": "Critical",
                "alert_status": "new",
                "triggered_rule_ids": ["rapid_pass_through"],
                "triggered_rule_count": 1,
                "explanation": "Suspicious indicator requires human review.",
                "first_activity_at": "2026-01-01T00:00:00+00:00",
                "last_activity_at": "2026-01-01T00:01:00+00:00",
                "incoming_amount_7d": 5000.0,
                "outgoing_amount_7d": 4900.0,
                "unique_senders_7d": 12,
                "unique_receivers_7d": 3,
                "hold_time_proxy_minutes": 15.0,
                "cluster_id": "CLUSTER_RUN_OKF_001",
                "source_data_fingerprint": "sourcehash",
                "rules_config_hash": "ruleshash",
                "created_at": "2026-01-01T00:02:00+00:00",
                "okf_concept_id": None,
                "transaction_description": "raw customer note",
                "customer_email": "person@example.com",
            }
        ]
    )
    alerts.to_parquet(run_dir / "alerts.parquet", index=False)

    evidence = pd.DataFrame(
        [
            {
                "run_id": "RUN_OKF",
                "account_id": alert_account,
                "rule_id": "rapid_pass_through",
                "rule_version": "1",
                "rule_weight": 35,
                "evaluation_status": "triggered",
                "triggered": True,
                "feature_values_json": json.dumps(
                    {"hold_time_proxy_minutes": 15, "pass_through_ratio_7d": 0.98}
                ),
                "thresholds_json": json.dumps(
                    {"hold_time_proxy_minutes_max": 120, "pass_through_ratio_7d": 0.8}
                ),
                "human_explanation": "rapid <script> pass-through indicator",
                "rules_config_hash": "ruleshash",
                "created_at": "2026-01-01T00:02:00+00:00",
                "transaction_description": "raw customer note",
            }
        ]
    )
    evidence.to_parquet(run_dir / "rule_evidence.parquet", index=False)

    graph_nodes = pd.DataFrame(
        [
            {
                "run_id": "RUN_OKF",
                "node_id": account_ids[0],
                "node_type": "Account",
                "label": account_ids[0],
                "account_id": account_ids[0],
                "cluster_id": "CLUSTER_RUN_OKF_001",
                "risk_score": 80,
                "risk_level": "Critical",
                "is_suspicious": True,
                "is_context": False,
                "alert_id": f"ALERT_RUN_OKF_{alert_account}",
                "triggered_rule_ids": ["rapid_pass_through"],
                "component_id": "COMPONENT_001",
                "short_cycle_member": True,
                "properties_json": "{}",
            },
            {
                "run_id": "RUN_OKF",
                "node_id": "ACC_CONTEXT",
                "node_type": "Account",
                "label": "ACC_CONTEXT",
                "account_id": "ACC_CONTEXT",
                "cluster_id": "CLUSTER_RUN_OKF_001",
                "risk_score": 10,
                "risk_level": "Low",
                "is_suspicious": False,
                "is_context": True,
                "alert_id": None,
                "triggered_rule_ids": [],
                "component_id": "COMPONENT_001",
                "short_cycle_member": False,
                "properties_json": "{}",
            },
            {
                "run_id": "RUN_OKF",
                "node_id": "CLUSTER_RUN_OKF_001",
                "node_type": "Cluster",
                "label": "CLUSTER_RUN_OKF_001",
                "account_id": None,
                "cluster_id": "CLUSTER_RUN_OKF_001",
                "risk_score": 80,
                "risk_level": "Critical",
                "is_suspicious": True,
                "is_context": False,
                "alert_id": None,
                "triggered_rule_ids": [],
                "component_id": "COMPONENT_001",
                "short_cycle_member": False,
                "properties_json": "{}",
            },
        ]
    )
    graph_nodes.to_parquet(run_dir / "graph_nodes.parquet", index=False)

    graph_edges = pd.DataFrame(
        [
            {
                "run_id": "RUN_OKF",
                "source_node_id": "ACC_CONTEXT",
                "target_node_id": account_ids[0],
                "edge_type": "TRANSFERRED_TO",
                "transaction_count": 2,
                "total_amount": 5000.0,
                "currency": "MYR",
                "first_seen_at": "2026-01-01T00:00:00+00:00",
                "last_seen_at": "2026-01-01T00:01:00+00:00",
                "sample_transaction_ids_json": json.dumps(["TX001", "TX002"]),
                "risk_relevance_score": 120.0,
                "component_id": "COMPONENT_001",
                "properties_json": "{}",
            },
            {
                "run_id": "RUN_OKF",
                "source_node_id": account_ids[0],
                "target_node_id": "CLUSTER_RUN_OKF_001",
                "edge_type": "MEMBER_OF_CLUSTER",
                "transaction_count": 0,
                "total_amount": 0.0,
                "currency": None,
                "first_seen_at": None,
                "last_seen_at": None,
                "sample_transaction_ids_json": "[]",
                "risk_relevance_score": 80.0,
                "component_id": "COMPONENT_001",
                "properties_json": "{}",
            },
        ]
    )
    graph_edges.to_parquet(run_dir / "graph_edges.parquet", index=False)

    clusters = pd.DataFrame(
        [
            {
                "run_id": "RUN_OKF",
                "cluster_id": "CLUSTER_RUN_OKF_001",
                "component_id": "COMPONENT_001",
                "account_count": 2,
                "suspicious_account_count": 1,
                "high_account_count": 0,
                "critical_account_count": 1,
                "transfer_edge_count": 1,
                "total_transfer_amount": 5000.0,
                "first_seen_at": "2026-01-01T00:00:00+00:00",
                "last_seen_at": "2026-01-01T00:01:00+00:00",
                "max_risk_score": 80,
                "risk_level_counts_json": json.dumps({"Critical": 1, "Low": 1}),
                "member_account_ids_json": json.dumps([account_ids[0], "ACC_CONTEXT"]),
                "suspicious_account_ids_json": json.dumps([account_ids[0]]),
                "short_cycle_detected": True,
                "short_cycle_account_ids_json": json.dumps([account_ids[0]]),
                "created_at": "2026-01-01T00:02:00+00:00",
                "human_review_note": "Suspicious connected account cluster requiring human review.",
            }
        ]
    )
    clusters.to_parquet(run_dir / "clusters.parquet", index=False)

    manifest = {
        "run_id": "RUN_OKF",
        "status": "phase4_complete",
        "source_data_fingerprint": "sourcehash",
        "rules_config_hash": "ruleshash",
        "code_commit": "abc123",
        "valid_row_count": 2,
        "rejected_row_count": 0,
        "duplicate_row_count": 0,
        "artifact_paths": {
            "account_risk": str(run_dir / "account_risk.parquet"),
            "alerts": str(run_dir / "alerts.parquet"),
            "rule_evidence": str(run_dir / "rule_evidence.parquet"),
            "graph_nodes": str(run_dir / "graph_nodes.parquet"),
            "graph_edges": str(run_dir / "graph_edges.parquet"),
            "clusters": str(run_dir / "clusters.parquet"),
            "run_manifest": str(run_dir / "run_manifest.json"),
        },
        "phase_status": {"phase5_okf": "pending"},
        "stage_timings_seconds": {},
    }
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    with duckdb.connect(str(run_dir / "transactions.duckdb")):
        pass
    return run_dir


def _concept_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.md") if path.name != "index.md")


def test_export_okf_bundle_writes_required_hierarchy(tmp_path):
    run_dir = _write_run_artifacts(tmp_path)
    config_path = _write_okf_config(tmp_path)

    result = export_okf_bundle(run_dir, okf_config_path=config_path)

    bundle = tmp_path / "okf_bundle"
    assert result.bundle_path == bundle
    assert (bundle / "index.md").exists()
    assert (bundle / "log.md").exists()
    assert (bundle / "accounts" / "ACC_MULE.md").exists()
    assert (bundle / "alerts" / "ALERT_RUN_OKF_ACC_MULE.md").exists()
    assert (bundle / "clusters" / "CLUSTER_RUN_OKF_001.md").exists()
    assert (bundle / "signals" / "rapid_pass_through.md").exists()
    assert (bundle / "runs" / "RUN_OKF.md").exists()
    assert (bundle / "datasets" / "transactions.md").exists()
    assert (bundle / "runbooks" / "mule_account_investigation.md").exists()
    assert (bundle / "okf_manifest.json").exists()
    assert 'okf_version: "0.1"' in (bundle / "index.md").read_text(encoding="utf-8")


def test_export_okf_bundle_uses_relative_links_and_excludes_private_text(tmp_path):
    run_dir = _write_run_artifacts(tmp_path)
    config_path = _write_okf_config(tmp_path)

    export_okf_bundle(run_dir, okf_config_path=config_path)

    bundle = tmp_path / "okf_bundle"
    text = (bundle / "accounts" / "ACC_MULE.md").read_text(encoding="utf-8")
    assert "[Rapid pass-through](../signals/rapid_pass_through.md)" in text
    assert "[Alert ALERT_RUN_OKF_ACC_MULE](../alerts/ALERT_RUN_OKF_ACC_MULE.md)" in text
    assert "[[rapid_pass_through]]" not in text
    assert "requires human review" in text
    assert "not a confirmed fraud" in text
    assert "raw customer note" not in text
    assert "person@example.com" not in text
    assert "&lt;script&gt;" in text


def test_export_okf_bundle_respects_limits_and_reserved_names(tmp_path):
    run_dir = _write_run_artifacts(tmp_path, reserved_accounts=True)
    config_path = _write_okf_config(
        tmp_path,
        limits={"max_accounts": 2, "max_alerts": 1, "max_clusters": 1},
    )

    export_okf_bundle(run_dir, okf_config_path=config_path)

    bundle = tmp_path / "okf_bundle"
    account_concepts = _concept_files(bundle / "accounts")
    assert len(account_concepts) == 2
    assert (bundle / "accounts" / "index_.md").exists()
    assert (bundle / "accounts" / "log_.md").exists()
    assert not (bundle / "transactions").exists()
    assert not (bundle / "raw_transactions").exists()

    account_risk = pd.read_parquet(run_dir / "account_risk.parquet").set_index("account_id")
    alerts = pd.read_parquet(run_dir / "alerts.parquet").set_index("account_id")
    assert account_risk.loc["index", "okf_concept_id"] == "accounts/index_"
    assert alerts.loc["index", "okf_concept_id"] == "alerts/ALERT_RUN_OKF_index"
