import json

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


def test_run_command_creates_phase3_artifacts(tmp_path):
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
    assert "Phase 3 complete" in result.output
    assert (run_dir / "normalized_transactions.parquet").exists()
    assert (run_dir / "rejected_rows.parquet").exists()
    assert (run_dir / "data_quality_report.json").exists()
    assert (run_dir / "run_manifest.json").exists()
    assert (run_dir / "account_features.parquet").exists()
    assert (run_dir / "account_risk.parquet").exists()
    assert (run_dir / "rule_evidence.parquet").exists()
    assert (run_dir / "alerts.parquet").exists()
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "phase3_complete"
    assert manifest["phase_status"]["phase3_features_scoring"] == "complete"
    assert manifest["artifact_paths"]["account_features"].endswith("account_features.parquet")


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
