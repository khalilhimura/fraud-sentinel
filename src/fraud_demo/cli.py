"""Command-line interface for the fraud demo."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from fraud_demo import __version__
from fraud_demo.config import load_rules_config
from fraud_demo.logging import configure_logging

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

    _ = (rows, output, seed)
    _phase_exit("Synthetic data generation", 2)


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
) -> None:
    """Validate and profile a transaction CSV."""

    _ = input_path
    _phase_exit("CSV validation and profiling", 2)


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
    force: Annotated[
        bool,
        typer.Option("--force", help="Allow replacing an existing run."),
    ] = False,
) -> None:
    """Run the complete fraud analysis pipeline."""

    _ = (input_path, run_id, force, load_rules_config())
    _phase_exit("Complete pipeline execution", 2)


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
