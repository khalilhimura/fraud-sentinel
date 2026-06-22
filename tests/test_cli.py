from typer.testing import CliRunner

from fraud_demo.cli import app


def test_cli_help_lists_required_commands():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ["generate-data", "profile", "run", "validate-okf", "monitor"]:
        assert command in result.output


def test_run_command_reports_phase_boundary(tmp_path):
    source = tmp_path / "transactions.csv"
    source.write_text(
        "transaction_id,event_timestamp,sender_account_id,receiver_account_id,amount,currency\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["run", "--input", str(source), "--run-id", "RUN_TEST"])

    assert result.exit_code != 0
    assert "Phase 2" in result.output
