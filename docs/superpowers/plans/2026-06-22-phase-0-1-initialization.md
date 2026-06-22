# Fraud Sentinel Phase 0-1 Initialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Initialize the repository through PRD Phase 0 and Phase 1 with a runnable Python package, typed configuration loading, CLI skeleton, project documentation, and smoke tests.

**Architecture:** Keep the first milestone intentionally thin: package boundaries, configuration models, logging setup, and CLI command stubs are created now, while ingestion, scoring, graph, OKF export, dashboard behavior, and monitoring remain explicit future phases. The scaffold mirrors the PRD structure so later phases can fill each module without reshaping the project.

**Tech Stack:** Python 3.12 target, DuckDB, Typer, Pydantic, PyYAML, Jinja2, NetworkX, Streamlit, Plotly, pytest, Ruff.

## Global Constraints

- Treat `agentic_ai_fraud_detection_okf_prd.md` as the source of truth until it is copied to `PRD.md`.
- The core pipeline must not require a runtime LLM or external API call.
- Fraud detection must remain deterministic and rule-based.
- Generated alerts must describe suspicious indicators requiring human review, not confirmed fraud.
- Raw transaction rows must not be exported as one Markdown concept per transaction.
- Large generated CSV, Parquet, DuckDB, and OKF output files must be ignored by Git.
- Phase 1 verification commands are `python -m fraud_demo --help` and `pytest -q`.
- Default local shell currently exposes Python 3.13.1; package metadata targets Python 3.12 or later to preserve the PRD target while allowing local verification.

---

## File Structure

- `PRD.md`: Canonical repo-local copy of the implementation-ready PRD.
- `AGENTS.md`: Agent operating rules distilled from the PRD.
- `IMPLEMENTATION_STATUS.md`: Phase tracker, assumptions, commands, and next work.
- `README.md`: Setup and Phase 1 usage instructions.
- `pyproject.toml`: Package metadata, dependencies, console script, pytest and Ruff settings.
- `Makefile`: Stable command aliases from the PRD.
- `.env.example`: Placeholder environment variables for optional future secrets.
- `.gitignore`: Prevents committing generated data, artifacts, caches, virtualenvs, and secrets.
- `config/*.yaml`: Default rule, pipeline, OKF, and dashboard settings from the PRD.
- `src/fraud_demo/__init__.py`: Package metadata.
- `src/fraud_demo/__main__.py`: `python -m fraud_demo` entrypoint.
- `src/fraud_demo/cli.py`: Typer app and command skeleton.
- `src/fraud_demo/config.py`: Pydantic models and YAML loading.
- `src/fraud_demo/logging.py`: Structured logging setup.
- `src/fraud_demo/*.py`: Future phase module stubs with clear `NotImplementedError` boundaries.
- `src/fraud_demo/templates/*.md.j2`: Placeholder template files for future OKF exporter work.
- `dashboard/app.py`, `dashboard/common.py`, `dashboard/pages/*.py`: Streamlit app shell and page placeholders.
- `tests/test_config.py`: Config loading and hashing smoke tests.
- `tests/test_cli.py`: CLI help smoke test.
- `tests/test_scaffold.py`: Module import smoke test.
- `scripts/*.sh`: Demo and benchmark command placeholders.

## Task 1: Documentation, Repository Metadata, And Static Scaffold

**Files:**
- Create: `PRD.md`
- Create: `AGENTS.md`
- Create: `IMPLEMENTATION_STATUS.md`
- Create: `README.md`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `Makefile`
- Create: `pyproject.toml`
- Create directories: `config/`, `data/raw/`, `data/incoming/`, `data/samples/`, `artifacts/okf_bundle/`, `artifacts/runs/`, `scripts/`, `src/fraud_demo/templates/`, `dashboard/pages/`, `tests/fixtures/`

**Interfaces:**
- Consumes: `agentic_ai_fraud_detection_okf_prd.md`.
- Produces: Project-level files and directories required by all later tasks.

- [ ] **Step 1: Create project metadata and docs**

Create the files listed above. `PRD.md` is a direct copy of `agentic_ai_fraud_detection_okf_prd.md`. `IMPLEMENTATION_STATUS.md` records Phase 0 complete, Phase 1 in progress, local Python version, missing DuckDB CLI, assumptions, and verification commands.

- [ ] **Step 2: Create ignored generated directories**

Add `.gitkeep` files only where the PRD expects empty input directories to exist: `data/.gitkeep`, `data/raw/.gitkeep`, `data/incoming/.gitkeep`, `data/samples/.gitkeep`, `tests/fixtures/.gitkeep`.

- [ ] **Step 3: Verify static scaffold**

Run: `find . -maxdepth 3 -type f | sort`

Expected: The repository contains the PRD copy, docs, config directory, package directory, dashboard directory, scripts directory, and tests directory.

## Task 2: Config Models With TDD

**Files:**
- Create: `tests/test_config.py`
- Create: `src/fraud_demo/config.py`
- Create: `config/rules.yaml`
- Create: `config/pipeline.yaml`
- Create: `config/okf.yaml`
- Create: `config/dashboard.yaml`

**Interfaces:**
- Produces: `load_rules_config(path: Path | str = "config/rules.yaml") -> RulesConfig`
- Produces: `file_sha256(path: Path | str) -> str`
- Produces: `canonical_yaml_hash(path: Path | str) -> str`

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path

from fraud_demo.config import canonical_yaml_hash, load_rules_config


def test_load_rules_config_reads_default_rules():
    config = load_rules_config(Path("config/rules.yaml"))

    assert config.version == "1.0"
    assert config.alert_min_score == 50
    assert config.rules["rapid_pass_through"].weight == 25
    assert config.rules["short_cycle"].thresholds["max_cycle_length"] == 5


def test_canonical_yaml_hash_is_stable_for_same_file():
    first = canonical_yaml_hash(Path("config/rules.yaml"))
    second = canonical_yaml_hash(Path("config/rules.yaml"))

    assert len(first) == 64
    assert first == second
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_config.py -q`

Expected: FAIL because `fraud_demo.config` does not exist.

- [ ] **Step 3: Implement config models and YAML files**

Implement Pydantic models for rule definitions and rule config loading. Add the PRD baseline rules to `config/rules.yaml` and small versioned defaults to `pipeline.yaml`, `okf.yaml`, and `dashboard.yaml`.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_config.py -q`

Expected: PASS.

## Task 3: CLI Skeleton With TDD

**Files:**
- Create: `tests/test_cli.py`
- Create: `src/fraud_demo/__init__.py`
- Create: `src/fraud_demo/__main__.py`
- Create: `src/fraud_demo/cli.py`
- Create: `src/fraud_demo/logging.py`

**Interfaces:**
- Produces: `fraud_demo.cli.app`
- Produces: `fraud_demo.cli.main() -> None`
- Produces Typer commands: `generate-data`, `profile`, `run`, `validate-okf`, `monitor`.

- [ ] **Step 1: Write failing CLI tests**

```python
from typer.testing import CliRunner

from fraud_demo.cli import app


def test_cli_help_lists_required_commands():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ["generate-data", "profile", "run", "validate-okf", "monitor"]:
        assert command in result.output


def test_run_command_reports_phase_boundary(tmp_path):
    source = tmp_path / "transactions.csv"
    source.write_text("transaction_id,event_timestamp,sender_account_id,receiver_account_id,amount,currency\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["run", "--input", str(source), "--run-id", "RUN_TEST"])

    assert result.exit_code != 0
    assert "Phase 2" in result.output
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_cli.py -q`

Expected: FAIL because `fraud_demo.cli` does not exist.

- [ ] **Step 3: Implement CLI skeleton**

Create Typer commands with PRD-compatible option names. Commands should validate obvious paths where useful, print phase-boundary messages, and raise `typer.Exit(2)` for unimplemented Phase 2+ behavior.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_cli.py -q`

Expected: PASS.

## Task 4: Future Module And Dashboard Placeholders

**Files:**
- Create: `tests/test_scaffold.py`
- Create: `src/fraud_demo/generate_data.py`
- Create: `src/fraud_demo/ingest.py`
- Create: `src/fraud_demo/profile.py`
- Create: `src/fraud_demo/features.py`
- Create: `src/fraud_demo/scoring.py`
- Create: `src/fraud_demo/graph_builder.py`
- Create: `src/fraud_demo/clusters.py`
- Create: `src/fraud_demo/alerts.py`
- Create: `src/fraud_demo/okf_exporter.py`
- Create: `src/fraud_demo/okf_validator.py`
- Create: `src/fraud_demo/monitoring.py`
- Create: `src/fraud_demo/manifests.py`
- Create: `src/fraud_demo/privacy.py`
- Create: `dashboard/app.py`
- Create: `dashboard/common.py`
- Create: `dashboard/pages/1_Overview.py`
- Create: `dashboard/pages/2_Alerts.py`
- Create: `dashboard/pages/3_Account_Investigation.py`
- Create: `dashboard/pages/4_Network_Explorer.py`
- Create: `dashboard/pages/5_OKF_Knowledge_Bundle.py`
- Create: `dashboard/pages/6_Monitoring.py`

**Interfaces:**
- Produces importable modules with explicit phase-boundary functions.

- [ ] **Step 1: Write failing scaffold tests**

```python
import importlib


def test_future_phase_modules_are_importable():
    for module_name in [
        "fraud_demo.generate_data",
        "fraud_demo.ingest",
        "fraud_demo.profile",
        "fraud_demo.features",
        "fraud_demo.scoring",
        "fraud_demo.graph_builder",
        "fraud_demo.clusters",
        "fraud_demo.alerts",
        "fraud_demo.okf_exporter",
        "fraud_demo.okf_validator",
        "fraud_demo.monitoring",
        "fraud_demo.manifests",
        "fraud_demo.privacy",
    ]:
        assert importlib.import_module(module_name)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_scaffold.py -q`

Expected: FAIL because future phase modules do not exist.

- [ ] **Step 3: Implement placeholders**

Create importable modules with docstrings and `raise NotImplementedError("Scheduled for Phase N")` functions where a future public boundary is obvious.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_scaffold.py -q`

Expected: PASS.

## Task 5: Phase 1 Verification And Initial Commit

**Files:**
- Modify: `IMPLEMENTATION_STATUS.md`

**Interfaces:**
- Consumes: All prior tasks.
- Produces: Verified Phase 1 scaffold and first Git commit if Git is available.

- [ ] **Step 1: Run CLI help verification**

Run: `python -m fraud_demo --help`

Expected: Exit code 0 and listed commands.

- [ ] **Step 2: Run full test suite**

Run: `pytest -q`

Expected: All tests pass.

- [ ] **Step 3: Update implementation status**

Record the exact verification commands and results in `IMPLEMENTATION_STATUS.md`.

- [ ] **Step 4: Initialize Git and commit**

Run:

```bash
git init
git add .
git commit -m "chore: initialize fraud sentinel scaffold"
```

Expected: First commit created. If Git identity or sandbox restrictions block the commit, record the blocker in `IMPLEMENTATION_STATUS.md` and report it.

## Self-Review

- Spec coverage: This plan covers PRD Phase 0 and Phase 1 only. It deliberately defers Phases 2-9 while creating named files and command placeholders for them.
- Placeholder scan: Future implementation placeholders are explicit phase boundaries in code, not ambiguous plan gaps.
- Type consistency: The plan consistently exposes `load_rules_config`, `canonical_yaml_hash`, `app`, and `main` for tests and later phases.
