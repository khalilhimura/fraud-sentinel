import importlib.util
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from dashboard.data import (
    build_account_investigation,
    build_bounded_graph,
    build_okf_summary,
    build_overview_metrics,
    filter_alerts,
    load_dashboard_artifacts,
    load_dashboard_config,
    load_okf_markdown_preview,
    prepare_alert_download,
)


def _write_dashboard_config(
    tmp_path: Path,
    *,
    max_nodes: int = 500,
    max_edges: int = 5000,
    max_counterparties: int = 30,
):
    config_path = tmp_path / "dashboard.yaml"
    config_path.write_text(
        "\n".join(
            [
                'version: "1.0"',
                f"default_artifacts_dir: {tmp_path / 'artifacts'}",
                f"default_okf_bundle: {tmp_path / 'okf_bundle'}",
                "cache_ttl_seconds: 1",
                "network_limits:",
                f"  max_nodes: {max_nodes}",
                f"  max_edges: {max_edges}",
                f"  max_counterparties_per_account: {max_counterparties}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return load_dashboard_config(config_path)


def _write_dashboard_run(
    tmp_path: Path,
    *,
    extra_graph_nodes: int = 0,
) -> Path:
    artifacts_dir = tmp_path / "artifacts"
    run_dir = artifacts_dir / "runs" / "RUN_DASH"
    bundle = tmp_path / "okf_bundle"
    run_dir.mkdir(parents=True)
    (bundle / "accounts").mkdir(parents=True)

    normalized = pd.DataFrame(
        [
            {
                "transaction_id": "TX_IN",
                "event_timestamp": "2026-01-01T00:00:00+00:00",
                "sender_account_id": "ACC_SOURCE",
                "receiver_account_id": "ACC_MULE",
                "amount": 1000.0,
                "currency": "MYR",
            },
            {
                "transaction_id": "TX_OUT",
                "event_timestamp": "2026-01-01T00:05:00+00:00",
                "sender_account_id": "ACC_MULE",
                "receiver_account_id": "ACC_OUT",
                "amount": 2000.0,
                "currency": "MYR",
            },
        ]
    )
    normalized.to_parquet(run_dir / "normalized_transactions.parquet", index=False)
    pd.DataFrame([{"transaction_id": "BAD_TX", "error": "invalid amount"}]).to_parquet(
        run_dir / "rejected_rows.parquet",
        index=False,
    )

    account_risk = pd.DataFrame(
        [
            {
                "run_id": "RUN_DASH",
                "account_id": "ACC_MULE",
                "risk_score": 85,
                "risk_level": "Critical",
                "triggered_rule_ids": ["rapid_pass_through"],
                "triggered_rule_count": 1,
                "incoming_amount_7d": 1000.0,
                "outgoing_amount_7d": 2000.0,
                "unique_senders_7d": 1,
                "unique_receivers_7d": 1,
                "hold_time_proxy_minutes": 5.0,
                "cluster_id": "CLUSTER_RUN_DASH_001",
                "okf_concept_id": "accounts/ACC_MULE",
                "created_at": "2026-01-01T00:06:00+00:00",
            },
            {
                "run_id": "RUN_DASH",
                "account_id": "ACC_HIGH",
                "risk_score": 55,
                "risk_level": "High",
                "triggered_rule_ids": ["high_fan_in"],
                "triggered_rule_count": 1,
                "incoming_amount_7d": 400.0,
                "outgoing_amount_7d": 50.0,
                "unique_senders_7d": 8,
                "unique_receivers_7d": 1,
                "hold_time_proxy_minutes": 90.0,
                "cluster_id": "CLUSTER_RUN_DASH_001",
                "okf_concept_id": "accounts/ACC_HIGH",
                "created_at": "2026-01-01T00:07:00+00:00",
            },
            {
                "run_id": "RUN_DASH",
                "account_id": "ACC_LOW",
                "risk_score": 5,
                "risk_level": "Low",
                "triggered_rule_ids": [],
                "triggered_rule_count": 0,
                "incoming_amount_7d": 10.0,
                "outgoing_amount_7d": 0.0,
                "unique_senders_7d": 1,
                "unique_receivers_7d": 0,
                "hold_time_proxy_minutes": None,
                "cluster_id": None,
                "okf_concept_id": None,
                "created_at": "2026-01-01T00:08:00+00:00",
            },
        ]
    )
    account_risk.to_parquet(run_dir / "account_risk.parquet", index=False)

    pd.DataFrame(
        [
            {
                "run_id": "RUN_DASH",
                "account_id": "ACC_MULE",
                "rule_id": "rapid_pass_through",
                "evaluation_status": "triggered",
                "triggered": True,
                "feature_values_json": json.dumps(
                    {"hold_time_proxy_minutes": 5, "pass_through_ratio_7d": 2.0}
                ),
                "thresholds_json": json.dumps(
                    {"hold_time_proxy_minutes_max": 120, "pass_through_ratio_7d": 0.8}
                ),
                "human_explanation": "rapid_pass_through triggered for review.",
            },
            {
                "run_id": "RUN_DASH",
                "account_id": "ACC_HIGH",
                "rule_id": "high_fan_in",
                "evaluation_status": "triggered",
                "triggered": True,
                "feature_values_json": json.dumps({"unique_senders_7d": 8}),
                "thresholds_json": json.dumps({"unique_senders_7d": 5}),
                "human_explanation": "high_fan_in triggered for review.",
            },
        ]
    ).to_parquet(run_dir / "rule_evidence.parquet", index=False)

    pd.DataFrame(
        [
            {
                "alert_id": "ALERT_RUN_DASH_ACC_MULE",
                "run_id": "RUN_DASH",
                "account_id": "ACC_MULE",
                "risk_score": 85,
                "risk_level": "Critical",
                "alert_status": "new",
                "triggered_rule_ids": ["rapid_pass_through"],
                "triggered_rule_count": 1,
                "explanation": "Suspicious indicator requires human review.",
                "first_activity_at": "2026-01-01T00:00:00+00:00",
                "last_activity_at": "2026-01-01T00:05:00+00:00",
                "incoming_amount_7d": 1000.0,
                "outgoing_amount_7d": 2000.0,
                "unique_senders_7d": 1,
                "unique_receivers_7d": 1,
                "hold_time_proxy_minutes": 5.0,
                "cluster_id": "CLUSTER_RUN_DASH_001",
                "created_at": "2026-01-01T00:06:00+00:00",
                "okf_concept_id": "alerts/ALERT_RUN_DASH_ACC_MULE",
            },
            {
                "alert_id": "ALERT_RUN_DASH_ACC_HIGH",
                "run_id": "RUN_DASH",
                "account_id": "ACC_HIGH",
                "risk_score": 55,
                "risk_level": "High",
                "alert_status": "new",
                "triggered_rule_ids": ["high_fan_in"],
                "triggered_rule_count": 1,
                "explanation": "Suspicious indicator requires human review.",
                "first_activity_at": "2026-01-01T00:00:00+00:00",
                "last_activity_at": "2026-01-01T00:07:00+00:00",
                "incoming_amount_7d": 400.0,
                "outgoing_amount_7d": 50.0,
                "unique_senders_7d": 8,
                "unique_receivers_7d": 1,
                "hold_time_proxy_minutes": 90.0,
                "cluster_id": "CLUSTER_RUN_DASH_001",
                "created_at": "2026-01-01T00:07:00+00:00",
                "okf_concept_id": "alerts/ALERT_RUN_DASH_ACC_HIGH",
            },
        ]
    ).to_parquet(run_dir / "alerts.parquet", index=False)

    graph_nodes = [
        {
            "run_id": "RUN_DASH",
            "node_id": "ACC_MULE",
            "node_type": "Account",
            "label": "ACC_MULE",
            "account_id": "ACC_MULE",
            "cluster_id": "CLUSTER_RUN_DASH_001",
            "risk_score": 85,
            "risk_level": "Critical",
            "is_suspicious": True,
            "is_context": False,
            "alert_id": "ALERT_RUN_DASH_ACC_MULE",
            "triggered_rule_ids": ["rapid_pass_through"],
            "component_id": "COMPONENT_001",
            "short_cycle_member": False,
            "properties_json": "{}",
        },
        {
            "run_id": "RUN_DASH",
            "node_id": "ACC_SOURCE",
            "node_type": "Account",
            "label": "ACC_SOURCE",
            "account_id": "ACC_SOURCE",
            "cluster_id": "CLUSTER_RUN_DASH_001",
            "risk_score": 5,
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
            "run_id": "RUN_DASH",
            "node_id": "ACC_OUT",
            "node_type": "Account",
            "label": "ACC_OUT",
            "account_id": "ACC_OUT",
            "cluster_id": "CLUSTER_RUN_DASH_001",
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
            "run_id": "RUN_DASH",
            "node_id": "CLUSTER_RUN_DASH_001",
            "node_type": "Cluster",
            "label": "CLUSTER_RUN_DASH_001",
            "account_id": None,
            "cluster_id": "CLUSTER_RUN_DASH_001",
            "risk_score": 85,
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
    graph_edges = [
        {
            "run_id": "RUN_DASH",
            "source_node_id": "ACC_SOURCE",
            "target_node_id": "ACC_MULE",
            "edge_type": "TRANSFERRED_TO",
            "transaction_count": 1,
            "total_amount": 1000.0,
            "currency": "MYR",
            "first_seen_at": "2026-01-01T00:00:00+00:00",
            "last_seen_at": "2026-01-01T00:00:00+00:00",
            "sample_transaction_ids_json": json.dumps(["TX_IN"]),
            "risk_relevance_score": 95.0,
            "component_id": "COMPONENT_001",
            "properties_json": "{}",
        },
        {
            "run_id": "RUN_DASH",
            "source_node_id": "ACC_MULE",
            "target_node_id": "ACC_OUT",
            "edge_type": "TRANSFERRED_TO",
            "transaction_count": 1,
            "total_amount": 2000.0,
            "currency": "MYR",
            "first_seen_at": "2026-01-01T00:05:00+00:00",
            "last_seen_at": "2026-01-01T00:05:00+00:00",
            "sample_transaction_ids_json": json.dumps(["TX_OUT"]),
            "risk_relevance_score": 105.0,
            "component_id": "COMPONENT_001",
            "properties_json": "{}",
        },
    ]
    for index in range(extra_graph_nodes):
        node_id = f"ACC_EXTRA_{index:03d}"
        graph_nodes.append(
            {
                **graph_nodes[1],
                "node_id": node_id,
                "label": node_id,
                "account_id": node_id,
                "risk_score": index,
            }
        )
        graph_edges.append(
            {
                **graph_edges[0],
                "source_node_id": node_id,
                "target_node_id": "ACC_MULE",
                "total_amount": float(100 + index),
                "risk_relevance_score": float(80 + index),
                "sample_transaction_ids_json": json.dumps([f"TX_EXTRA_{index:03d}"]),
            }
        )

    pd.DataFrame(graph_nodes).to_parquet(run_dir / "graph_nodes.parquet", index=False)
    pd.DataFrame(graph_edges).to_parquet(run_dir / "graph_edges.parquet", index=False)

    pd.DataFrame(
        [
            {
                "run_id": "RUN_DASH",
                "cluster_id": "CLUSTER_RUN_DASH_001",
                "component_id": "COMPONENT_001",
                "account_count": 3,
                "suspicious_account_count": 2,
                "high_account_count": 1,
                "critical_account_count": 1,
                "transfer_edge_count": 2,
                "total_transfer_amount": 3000.0,
                "first_seen_at": "2026-01-01T00:00:00+00:00",
                "last_seen_at": "2026-01-01T00:05:00+00:00",
                "max_risk_score": 85,
                "risk_level_counts_json": json.dumps({"Critical": 1, "High": 1, "Low": 1}),
                "member_account_ids_json": json.dumps(["ACC_MULE", "ACC_SOURCE", "ACC_OUT"]),
                "suspicious_account_ids_json": json.dumps(["ACC_MULE", "ACC_HIGH"]),
                "short_cycle_detected": False,
                "short_cycle_account_ids_json": "[]",
                "created_at": "2026-01-01T00:09:00+00:00",
                "human_review_note": "Suspicious connected account cluster requiring human review.",
            }
        ]
    ).to_parquet(run_dir / "clusters.parquet", index=False)

    data_quality_report = {
        "valid_row_count": 10,
        "rejected_row_count": 1,
        "generated_at": "2026-01-01T00:10:00+00:00",
    }
    (run_dir / "data_quality_report.json").write_text(
        json.dumps(data_quality_report, indent=2),
        encoding="utf-8",
    )

    okf_manifest = {
        "okf_version": "0.1",
        "bundle_path": str(bundle),
        "run_id": "RUN_DASH",
        "concept_count": 4,
        "counts": {"accounts": 2, "alerts": 2, "clusters": 1, "signals": 2},
    }
    (bundle / "okf_manifest.json").write_text(
        json.dumps(okf_manifest, indent=2),
        encoding="utf-8",
    )
    validation_report = {
        "okf_version": "0.1",
        "bundle_path": str(bundle),
        "valid": True,
        "concept_count": 4,
        "link_count": 7,
        "hard_errors": [],
        "warnings": [],
    }
    (run_dir / "okf_validation_report.json").write_text(
        json.dumps(validation_report, indent=2),
        encoding="utf-8",
    )
    (bundle / "accounts" / "ACC_MULE.md").write_text(
        "---\ntype: Fraud Account\ntitle: Account ACC_MULE\n---\n# Account ACC_MULE\n\n"
        "Suspicious indicator requiring human review, not a confirmed fraud judgment.\n",
        encoding="utf-8",
    )

    manifest = {
        "run_id": "RUN_DASH",
        "status": "phase5_complete",
        "completed_at": "2026-01-01T00:11:00+00:00",
        "source_files": [str(tmp_path / "input.csv")],
        "source_file_fingerprints": {str(tmp_path / "input.csv"): "filehash"},
        "source_data_fingerprint": "sourcehash",
        "valid_row_count": 10,
        "rejected_row_count": 1,
        "distinct_account_count": 4,
        "alert_count": 2,
        "cluster_count": 1,
        "stage_timings_seconds": {"ingest": 1.2, "okf_export": 0.3},
        "phase_status": {
            "phase5_okf": "complete",
            "phase6_dashboard": "pending",
            "phase7_monitoring": "pending",
        },
        "artifact_paths": {
            "data_quality_report": str(run_dir / "data_quality_report.json"),
            "normalized_transactions": str(run_dir / "normalized_transactions.parquet"),
            "rejected_rows": str(run_dir / "rejected_rows.parquet"),
            "account_risk": str(run_dir / "account_risk.parquet"),
            "rule_evidence": str(run_dir / "rule_evidence.parquet"),
            "alerts": str(run_dir / "alerts.parquet"),
            "graph_nodes": str(run_dir / "graph_nodes.parquet"),
            "graph_edges": str(run_dir / "graph_edges.parquet"),
            "clusters": str(run_dir / "clusters.parquet"),
            "okf_bundle": str(bundle),
            "okf_manifest": str(bundle / "okf_manifest.json"),
            "okf_validation_report": str(run_dir / "okf_validation_report.json"),
            "run_manifest": str(run_dir / "run_manifest.json"),
        },
    }
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return run_dir


def test_dashboard_artifact_loading_never_reads_raw_csv(tmp_path, monkeypatch):
    run_dir = _write_dashboard_run(tmp_path)
    config = _write_dashboard_config(tmp_path)

    def fail_read_csv(*args, **kwargs):
        raise AssertionError("raw CSV read")

    monkeypatch.setattr(pd, "read_csv", fail_read_csv)

    artifacts = load_dashboard_artifacts(run_dir, config)

    assert artifacts.manifest["run_id"] == "RUN_DASH"
    assert len(artifacts.frames["alerts"]) == 2
    assert artifacts.missing_artifacts == ()


def test_missing_artifact_handling_reports_empty_frame(tmp_path):
    run_dir = _write_dashboard_run(tmp_path)
    config = _write_dashboard_config(tmp_path)
    (run_dir / "graph_edges.parquet").unlink()

    artifacts = load_dashboard_artifacts(run_dir, config)

    assert "graph_edges" in artifacts.missing_artifacts
    assert artifacts.frames["graph_edges"].empty


def test_overview_metrics_use_manifest_and_prepared_frames(tmp_path):
    artifacts = load_dashboard_artifacts(
        _write_dashboard_run(tmp_path),
        _write_dashboard_config(tmp_path),
    )

    metrics = build_overview_metrics(artifacts)

    assert metrics["valid_row_count"] == 10
    assert metrics["rejected_row_count"] == 1
    assert metrics["distinct_account_count"] == 4
    assert metrics["high_critical_alert_count"] == 2
    assert metrics["suspicious_cluster_count"] == 1
    assert metrics["suspicious_transfer_amount"] == 3000.0
    assert metrics["run_id"] == "RUN_DASH"
    assert metrics["source_data_fingerprint"] == "sourcehash"


def test_alert_filters_and_download_prepare_prd_columns(tmp_path):
    artifacts = load_dashboard_artifacts(
        _write_dashboard_run(tmp_path),
        _write_dashboard_config(tmp_path),
    )

    filtered = filter_alerts(
        artifacts.frames["alerts"],
        {
            "risk_levels": ["Critical"],
            "min_score": 80,
            "triggered_rule": "rapid_pass_through",
            "cluster_id": "CLUSTER_RUN_DASH_001",
            "date_range": (date(2026, 1, 1), date(2026, 1, 1)),
        },
    )

    assert filtered["alert_id"].tolist() == ["ALERT_RUN_DASH_ACC_MULE"]
    assert b"alert_id,account_id,risk_score" in prepare_alert_download(filtered)
    assert b"ALERT_RUN_DASH_ACC_MULE" in prepare_alert_download(filtered)


def test_account_investigation_joins_evidence_counterparties_cluster_and_okf(tmp_path):
    artifacts = load_dashboard_artifacts(
        _write_dashboard_run(tmp_path),
        _write_dashboard_config(tmp_path),
    )

    investigation = build_account_investigation(artifacts, "ACC_MULE")

    assert investigation["account"]["account_id"] == "ACC_MULE"
    assert investigation["account"]["risk_score"] == 85
    assert investigation["okf_concept_id"] == "accounts/ACC_MULE"
    assert investigation["cluster"]["cluster_id"] == "CLUSTER_RUN_DASH_001"
    assert investigation["incoming_summary"]["transaction_count"] == 1
    assert investigation["outgoing_summary"]["transaction_count"] == 1
    assert investigation["rule_evidence"]["rule_id"].tolist() == ["rapid_pass_through"]
    assert investigation["top_counterparties"]["node_id"].tolist() == ["ACC_OUT", "ACC_SOURCE"]


def test_bounded_graph_enforces_dashboard_limits_before_render(tmp_path):
    artifacts = load_dashboard_artifacts(
        _write_dashboard_run(tmp_path, extra_graph_nodes=20),
        _write_dashboard_config(tmp_path, max_nodes=3, max_edges=2),
    )

    graph = build_bounded_graph(artifacts, {"account_id": "ACC_MULE", "depth": 2})

    assert len(graph["nodes"]) <= 3
    assert len(graph["edges"]) <= 2
    assert graph["limits"]["max_nodes"] == 3
    assert graph["limits"]["max_edges"] == 2


def test_okf_summary_and_markdown_preview(tmp_path):
    artifacts = load_dashboard_artifacts(
        _write_dashboard_run(tmp_path),
        _write_dashboard_config(tmp_path),
    )

    summary = build_okf_summary(artifacts)
    preview = load_okf_markdown_preview(artifacts.okf_bundle_path, "accounts/ACC_MULE")

    assert summary["okf_version"] == "0.1"
    assert summary["concept_count"] == 4
    assert summary["link_count"] == 7
    assert summary["validation_valid"] is True
    assert summary["bundle_path"] == str(tmp_path / "okf_bundle")
    assert "Account ACC_MULE" in preview
    assert "human review" in preview


def test_dashboard_pages_import_without_crashing():
    for path in sorted(Path("dashboard/pages").glob("*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)


def test_dashboard_modules_expose_render_functions():
    from dashboard.app import render_app

    assert callable(render_app)
    for path in sorted(Path("dashboard/pages").glob("*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        assert callable(module.render_page)


def test_dashboard_app_imports_when_streamlit_uses_script_directory():
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, "dashboard/app.py"],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
