"""Command-line interface for the fraud demo."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Annotated

import typer

from fraud_demo import __version__
from fraud_demo.alerts import generate_alerts
from fraud_demo.clusters import identify_clusters
from fraud_demo.features import compute_account_features
from fraud_demo.generate_data import generate_synthetic_transactions
from fraud_demo.graph_builder import build_graph_artifacts
from fraud_demo.ingest import ingest_transactions
from fraud_demo.logging import configure_logging
from fraud_demo.manifests import (
    build_phase2_manifest,
    build_phase3_manifest,
    build_phase4_manifest,
    write_run_manifest,
)
from fraud_demo.profile import profile_run
from fraud_demo.scoring import score_accounts

app = typer.Typer(
    add_completion=False,
    help="Deterministic mule-account fraud detection demo with OKF export.",
    no_args_is_help=True,
)


def _version_callback(show_version: bool) -> None:
    if show_version:
        typer.echo(f"fraud-sentinel {__version__}")
        raise typer.Exit()


@app.callback()
def callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the package version and exit.",
        ),
    ] = False,
) -> None:
    """Fraud Sentinel command surface."""

    configure_logging()


def _phase_exit(message: str, phase: int) -> None:
    typer.echo(f"{message} is scheduled for Phase {phase}.")
    raise typer.Exit(2)


@app.command("generate-data")
def generate_data(
    output: Annotated[Path, typer.Option("--output", help="Output CSV path.")],
    rows: Annotated[
        int,
        typer.Option(min=1, help="Number of synthetic rows to create."),
    ] = 1_000_000,
    seed: Annotated[int, typer.Option(help="Random seed.")] = 42,
) -> None:
    """Generate reproducible synthetic transactions."""

    result = generate_synthetic_transactions(rows=rows, output=output, seed=seed)
    typer.echo(
        f"Generated {result.row_count} rows at {result.output_path}. "
        f"Scenario manifest: {result.scenario_manifest_path}"
    )


@app.command("profile")
def profile(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Input transaction CSV.",
        ),
    ],
    run_id: Annotated[
        str | None,
        typer.Option("--run-id", help="Profile run identifier."),
    ] = None,
    artifacts_dir: Annotated[
        Path,
        typer.Option("--artifacts-dir", help="Artifacts root directory."),
    ] = Path("artifacts"),
    force: Annotated[
        bool,
        typer.Option("--force", help="Allow replacing an existing profile run."),
    ] = False,
) -> None:
    """Validate and profile a transaction CSV."""

    actual_run_id = run_id or f"PROFILE_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    ingestion = ingest_transactions(
        [input_path],
        run_id=actual_run_id,
        artifacts_dir=artifacts_dir,
        force=force,
    )
    report = profile_run(ingestion.run_dir, ingestion.source_data_fingerprint)
    manifest = build_phase2_manifest(ingestion, report)
    manifest_path = write_run_manifest(ingestion.run_dir, manifest)
    typer.echo(
        f"Profile complete for {actual_run_id}. "
        f"Valid rows: {ingestion.valid_row_count}. "
        f"Rejected rows: {ingestion.rejected_row_count}. "
        f"Manifest: {manifest_path}"
    )


@app.command("run")
def run_pipeline(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Input transaction CSV.",
        ),
    ],
    run_id: Annotated[str, typer.Option("--run-id", help="Pipeline run identifier.")],
    artifacts_dir: Annotated[
        Path,
        typer.Option("--artifacts-dir", help="Artifacts root directory."),
    ] = Path("artifacts"),
    force: Annotated[
        bool,
        typer.Option("--force", help="Allow replacing an existing run."),
    ] = False,
) -> None:
    """Run the complete fraud analysis pipeline."""

    ingestion = ingest_transactions(
        [input_path],
        run_id=run_id,
        artifacts_dir=artifacts_dir,
        force=force,
    )
    report = profile_run(ingestion.run_dir, ingestion.source_data_fingerprint)
    phase2_manifest = build_phase2_manifest(ingestion, report)

    stage_timings: dict[str, float] = {}
    started_at = perf_counter()
    feature_result = compute_account_features(ingestion.run_dir)
    stage_timings["feature_engineering"] = round(perf_counter() - started_at, 6)

    started_at = perf_counter()
    scoring_result = score_accounts(ingestion.run_dir)
    stage_timings["scoring"] = round(perf_counter() - started_at, 6)

    started_at = perf_counter()
    alert_result = generate_alerts(ingestion.run_dir)
    stage_timings["alert_generation"] = round(perf_counter() - started_at, 6)

    phase3_manifest = build_phase3_manifest(
        phase2_manifest,
        feature_result,
        scoring_result,
        alert_result,
        stage_timings,
    )

    started_at = perf_counter()
    graph_result = build_graph_artifacts(ingestion.run_dir)
    stage_timings["graph_build"] = round(perf_counter() - started_at, 6)

    started_at = perf_counter()
    cluster_result = identify_clusters(ingestion.run_dir)
    stage_timings["clustering"] = round(perf_counter() - started_at, 6)

    manifest = build_phase4_manifest(
        phase3_manifest,
        graph_result,
        cluster_result,
        stage_timings,
    )
    manifest_path = write_run_manifest(ingestion.run_dir, manifest)
    typer.echo(
        f"Phase 4 complete for {run_id}. "
        f"Valid rows: {ingestion.valid_row_count}. "
        f"Rejected rows: {ingestion.rejected_row_count}. "
        f"Duplicate rows removed: {ingestion.duplicate_row_count}. "
        f"Accounts scored: {feature_result.account_count}. "
        f"Alerts: {alert_result.alert_count}. "
        f"Clusters: {cluster_result.cluster_count}. "
        f"Manifest: {manifest_path}"
    )


@app.command("validate-okf")
def validate_okf(
    bundle: Annotated[Path, typer.Option("--bundle", help="OKF bundle directory.")],
) -> None:
    """Validate an existing OKF bundle."""

    _ = bundle
    _phase_exit("OKF validation", 5)


@app.command("monitor")
def monitor(
    inbox: Annotated[
        Path,
        typer.Option("--inbox", help="Directory containing incoming CSV files."),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", help="Reprocess files already seen."),
    ] = False,
) -> None:
    """Process new files from the incoming directory."""

    _ = (inbox, force)
    _phase_exit("File-based monitoring", 7)


def main() -> None:
    """Run the CLI app."""

    app()
