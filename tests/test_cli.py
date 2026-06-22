import json
from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from fraud_demo.cli import app


def test_cli_help_lists_required_commands():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ["generate-data", "profile", "run", "validate-okf", "monitor"]:
        assert command in result.output


def test_generate_data_command_creates_csv_and_manifest(tmp_path):
    output = tmp_path / "transactions.csv"

    result = CliRunner().invoke(
        app,
        ["generate-data", "--rows", "100", "--output", str(output), "--seed", "42"],
    )

    assert result.exit_code == 0
    assert output.exists()
    assert output.with_suffix(".scenario_manifest.json").exists()
    assert "100 rows" in result.output


def test_run_command_creates_phase5_artifacts(tmp_path):
    source = tmp_path / "transactions.csv"
    source.write_text(
        "\n".join(
            [
                "transaction_id,event_timestamp,sender_account_id,receiver_account_id,amount,currency",
                "TX001,2026-01-01T00:00:00Z,ACC_A,ACC_B,10.50,MYR",
                "TX002,2026-01-01T00:01:00Z,ACC_B,ACC_C,20.00,MYR",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "run",
            "--input",
            str(source),
            "--run-id",
            "RUN_TEST",
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
        ],
    )

    run_dir = tmp_path / "artifacts" / "runs" / "RUN_TEST"
    assert result.exit_code == 0
    assert "Phase 5 complete" in result.output
    assert (run_dir / "normalized_transactions.parquet").exists()
    assert (run_dir / "rejected_rows.parquet").exists()
    assert (run_dir / "data_quality_report.json").exists()
    assert (run_dir / "run_manifest.json").exists()
    assert (run_dir / "account_features.parquet").exists()
    assert (run_dir / "account_risk.parquet").exists()
    assert (run_dir / "rule_evidence.parquet").exists()
    assert (run_dir / "alerts.parquet").exists()
    assert (run_dir / "graph_nodes.parquet").exists()
    assert (run_dir / "graph_edges.parquet").exists()
    assert (run_dir / "clusters.parquet").exists()
    assert (run_dir / "okf_validation_report.json").exists()
    assert (Path("artifacts") / "okf_bundle" / "index.md").exists()
    assert (Path("artifacts") / "okf_bundle" / "okf_manifest.json").exists()
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "phase5_complete"
    assert manifest["phase_status"]["phase3_features_scoring"] == "complete"
    assert manifest["phase_status"]["phase4_graph_clusters"] == "complete"
    assert manifest["phase_status"]["phase5_okf"] == "complete"
    assert manifest["artifact_paths"]["account_features"].endswith("account_features.parquet")
    assert manifest["artifact_paths"]["graph_nodes"].endswith("graph_nodes.parquet")
    assert manifest["artifact_paths"]["graph_edges"].endswith("graph_edges.parquet")
    assert manifest["artifact_paths"]["clusters"].endswith("clusters.parquet")
    assert manifest["artifact_paths"]["okf_bundle"].endswith("okf_bundle")
    assert manifest["artifact_paths"]["okf_manifest"].endswith("okf_manifest.json")
    assert manifest["artifact_paths"]["okf_validation_report"].endswith(
        "okf_validation_report.json"
    )
    assert "graph_build" in manifest["stage_timings_seconds"]
    assert "clustering" in manifest["stage_timings_seconds"]
    assert "okf_export" in manifest["stage_timings_seconds"]
    assert "okf_validate" in manifest["stage_timings_seconds"]
    assert "cluster_count" in manifest


def test_validate_okf_command_validates_bundle(tmp_path):
    bundle = tmp_path / "okf_bundle"
    (bundle / "accounts").mkdir(parents=True)
    (bundle / "index.md").write_text('---\nokf_version: "0.1"\n---\n\n# Bundle\n', encoding="utf-8")
    (bundle / "log.md").write_text("# Log\n\n## 2026-06-22\n\n- Created.\n", encoding="utf-8")
    (bundle / "accounts" / "index.md").write_text("# Accounts\n", encoding="utf-8")
    (bundle / "accounts" / "ACC001.md").write_text(
        "---\ntype: Fraud Account\ntitle: Account ACC001\ndescription: Test\n---\n# Account\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["validate-okf", "--bundle", str(bundle)])

    assert result.exit_code == 0
    assert "OKF valid" in result.output


def test_run_command_alerts_on_generated_scenarios(tmp_path):
    source = tmp_path / "generated.csv"
    artifacts = tmp_path / "artifacts"

    generated = CliRunner().invoke(
        app,
        ["generate-data", "--rows", "120", "--output", str(source), "--seed", "42"],
    )
    assert generated.exit_code == 0

    result = CliRunner().invoke(
        app,
        [
            "run",
            "--input",
            str(source),
            "--run-id",
            "RUN_GENERATED",
            "--artifacts-dir",
            str(artifacts),
        ],
    )

    assert result.exit_code == 0
    alerts = pd.read_parquet(artifacts / "runs" / "RUN_GENERATED" / "alerts.parquet")
    assert len(alerts) >= 1
    assert alerts["explanation"].str.contains("requires human review").all()
