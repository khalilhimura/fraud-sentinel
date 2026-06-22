# Phase 5 OKF Export And Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Phase 5 OKF v0.1 bundle export, validation, CLI wiring, manifest updates, and status documentation.

**Architecture:** `okf_exporter.py` loads the Phase 4 run artifacts, selects bounded concepts from configured limits, renders Jinja2 Markdown templates, writes the bundle hierarchy, updates concept IDs in run artifacts, and emits `okf_manifest.json`. `okf_validator.py` validates reserved files, frontmatter, links, relations, privacy patterns, and report schema. `cli.py` runs export plus validation after Phase 4 and exposes `validate-okf`.

**Tech Stack:** Python 3.12+, pandas, PyYAML, Jinja2, DuckDB, Typer, pytest, Ruff.

## Global Constraints

- Treat `PRD.md` as the source of truth.
- Follow AGENTS.md Phase 5 rules.
- Do not send raw transaction data to external models or APIs.
- Use synthetic or approved anonymized data only.
- Keep fraud detection deterministic and rule-based.
- Label outputs as suspicious indicators requiring human review, not confirmed fraud.
- Preserve run provenance, configuration hashes, source fingerprints, and stage timings.
- Do not generate one Markdown file per raw transaction.
- Use standard relative Markdown links, not Wikilinks.
- Include typed relations frontmatter only when configured and keep Markdown body links mandatory.
- Respect `config/okf.yaml` export limits and privacy flags.
- Never weaken or delete valid tests just to make the suite pass.

---

## File Structure

- Modify `src/fraud_demo/okf_exporter.py`: config loading, concept selection, rendering, bundle writes, artifact updates, DuckDB registration.
- Modify `src/fraud_demo/okf_validator.py`: OKF validation result model, frontmatter parsing, link validation, relation checks, privacy scanner, report writing.
- Modify `src/fraud_demo/templates/account.md.j2`: account concept frontmatter and body.
- Modify `src/fraud_demo/templates/alert.md.j2`: alert concept frontmatter and body.
- Modify `src/fraud_demo/templates/cluster.md.j2`: cluster concept frontmatter and body.
- Modify `src/fraud_demo/templates/signal.md.j2`: signal concept frontmatter and body.
- Modify `src/fraud_demo/templates/run.md.j2`: run concept frontmatter and body.
- Modify `src/fraud_demo/templates/runbook.md.j2`: runbook concept frontmatter and body.
- Modify `src/fraud_demo/manifests.py`: Phase 5 manifest builder.
- Modify `src/fraud_demo/cli.py`: `run` Phase 5 orchestration and `validate-okf` command.
- Add `tests/test_okf_exporter.py`: exporter TDD coverage.
- Add `tests/test_okf_validator.py`: validator TDD coverage.
- Modify `tests/test_cli.py`: Phase 5 CLI and manifest assertions.
- Modify `IMPLEMENTATION_STATUS.md`: Phase 5 status, assumptions, and verification evidence.

## Task 1: Exporter Bundle Hierarchy And Concepts

**Files:**
- Modify: `src/fraud_demo/okf_exporter.py`
- Modify: `src/fraud_demo/templates/*.j2`
- Test: `tests/test_okf_exporter.py`

**Interfaces:**
- Produces: `OkfExportResult`
- Produces: `export_okf_bundle(run_dir: Path | str, *, okf_config_path: Path | str = "config/okf.yaml", rules_path: Path | str = "config/rules.yaml") -> OkfExportResult`

- [ ] **Step 1: Write failing exporter hierarchy test**

Create a Phase 4-style run fixture with `account_risk.parquet`, `alerts.parquet`, `rule_evidence.parquet`, `graph_nodes.parquet`, `graph_edges.parquet`, `clusters.parquet`, `transactions.duckdb`, and `run_manifest.json`. Assert `export_okf_bundle(run_dir, okf_config_path=tmp_okf_config)` writes:

```python
bundle = tmp_path / "okf_bundle"
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
```

- [ ] **Step 2: Run hierarchy test to verify failure**

Run: `.venv/bin/pytest tests/test_okf_exporter.py::test_export_okf_bundle_writes_required_hierarchy -q`

Expected: FAIL because `export_okf_bundle` is still a Phase 5 placeholder.

- [ ] **Step 3: Implement minimal hierarchy and rendering**

Implement OKF config loading, deterministic output cleanup for generated files, directory creation, Jinja2 environment with autoescape disabled for Markdown, frontmatter YAML rendering via `yaml.safe_dump`, template rendering for the seven required concept groups, root/subdirectory indexes, `log.md`, and `okf_manifest.json`.

- [ ] **Step 4: Run hierarchy test to verify pass**

Run: `.venv/bin/pytest tests/test_okf_exporter.py::test_export_okf_bundle_writes_required_hierarchy -q`

Expected: PASS.

- [ ] **Step 5: Write failing links, privacy, and escaping test**

Assert generated Markdown:

```python
text = (bundle / "accounts" / "ACC_MULE.md").read_text(encoding="utf-8")
assert "[Rapid pass-through](../signals/rapid_pass_through.md)" in text
assert "[Alert ALERT_RUN_OKF_ACC_MULE](../alerts/ALERT_RUN_OKF_ACC_MULE.md)" in text
assert "[[rapid_pass_through]]" not in text
assert "requires human review" in text
assert "not a confirmed fraud" in text
assert "raw customer note" not in text
assert "&lt;script&gt;" in text
```

- [ ] **Step 6: Run links/privacy test to verify failure**

Run: `.venv/bin/pytest tests/test_okf_exporter.py::test_export_okf_bundle_uses_relative_links_and_excludes_private_text -q`

Expected: FAIL until templates sanitize Markdown body values and exclude private fields.

- [ ] **Step 7: Complete templates, safe text, and relation payloads**

Add reusable Markdown/HTML escaping helpers for table/body cells, sanitize filenames, build concept IDs, build relative links, include typed relation frontmatter when enabled, and pass complete template contexts for accounts, alerts, clusters, signals, run, dataset, and runbook concepts.

- [ ] **Step 8: Write failing export limits and reserved filename test**

Use a config with `max_accounts: 1`, `max_alerts: 1`, and `max_clusters: 1`; include account IDs `index`, `log`, and `ACC_MULE`. Assert only one account concept is exported, reserved names are suffixed, and no raw transaction concept directory is created.

- [ ] **Step 9: Run limits/reserved test to verify failure**

Run: `.venv/bin/pytest tests/test_okf_exporter.py::test_export_okf_bundle_respects_limits_and_reserved_names -q`

Expected: FAIL until limits and reserved filename rules are enforced.

- [ ] **Step 10: Complete exporter behavior**

Enforce account, alert, and cluster caps; reserve `index` and `log`; avoid raw transaction note generation; update `account_risk.parquet` and `alerts.parquet` `okf_concept_id` fields; update DuckDB tables; return accurate result counts.

- [ ] **Step 11: Run exporter tests**

Run: `.venv/bin/pytest tests/test_okf_exporter.py -q`

Expected: PASS.

## Task 2: OKF Validator

**Files:**
- Modify: `src/fraud_demo/okf_validator.py`
- Test: `tests/test_okf_validator.py`

**Interfaces:**
- Produces: `OkfValidationResult`
- Produces: `validate_okf_bundle(bundle: Path | str, *, report_path: Path | str | None = None, max_file_size_bytes: int = 512_000) -> OkfValidationResult`

- [ ] **Step 1: Write failing validator success/report test**

Create a minimal valid bundle with root `index.md`, `log.md`, a subdirectory `index.md`, and `accounts/ACC001.md` with frontmatter. Assert:

```python
result = validate_okf_bundle(bundle, report_path=report_path)
assert result.valid is True
assert result.concept_count == 1
assert result.link_count == 0
assert report_path.exists()
report = json.loads(report_path.read_text(encoding="utf-8"))
assert report["valid"] is True
assert report["hard_errors"] == []
```

- [ ] **Step 2: Run validator success test to verify failure**

Run: `.venv/bin/pytest tests/test_okf_validator.py::test_validate_okf_bundle_accepts_valid_bundle_and_writes_report -q`

Expected: FAIL because the validator is still a placeholder.

- [ ] **Step 3: Implement minimal validator**

Read all Markdown as UTF-8, distinguish reserved files, parse YAML frontmatter for concept files, require non-empty `type`, count concepts and links, build the report schema, and set `valid` from hard error count.

- [ ] **Step 4: Run validator success test to verify pass**

Run: `.venv/bin/pytest tests/test_okf_validator.py::test_validate_okf_bundle_accepts_valid_bundle_and_writes_report -q`

Expected: PASS.

- [ ] **Step 5: Write failing hard error test**

Create non-reserved Markdown without frontmatter, Markdown with invalid YAML, and Markdown with empty `type`. Assert `valid is False` and hard error codes include `missing_frontmatter`, `invalid_frontmatter`, and `missing_type`.

- [ ] **Step 6: Run hard error test to verify failure**

Run: `.venv/bin/pytest tests/test_okf_validator.py::test_validate_okf_bundle_reports_hard_frontmatter_errors -q`

Expected: FAIL until all hard errors are implemented.

- [ ] **Step 7: Complete hard validation rules**

Add reserved-file structure checks, duplicate concept ID defense, path containment checks, and invalid UTF-8 handling.

- [ ] **Step 8: Write failing warning test**

Create a concept linking to a missing internal Markdown file and a `relations` target that does not exist. Assert `valid is True` and warnings include `broken_link`, `broken_relation`, and `missing_directory_index`.

- [ ] **Step 9: Run warning test to verify failure**

Run: `.venv/bin/pytest tests/test_okf_validator.py::test_validate_okf_bundle_warns_for_broken_links_relations_and_indexes -q`

Expected: FAIL until warning checks are implemented.

- [ ] **Step 10: Complete warning checks and privacy scanner**

Resolve standard Markdown relative links, skip external URLs and anchors, validate `relations[].target_concept_id`, warn on missing recommended fields, file size, timestamp format, directory indexes, and common PII/privacy terms.

- [ ] **Step 11: Run validator tests**

Run: `.venv/bin/pytest tests/test_okf_validator.py -q`

Expected: PASS.

## Task 3: CLI And Manifest Integration

**Files:**
- Modify: `src/fraud_demo/manifests.py`
- Modify: `src/fraud_demo/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `export_okf_bundle`, `validate_okf_bundle`
- Produces: `build_phase5_manifest(phase4_manifest: dict[str, Any], export_result: Any, validation_result: Any, stage_timings_seconds: dict[str, float]) -> dict[str, Any]`
- Produces: `python -m fraud_demo validate-okf --bundle artifacts/okf_bundle`

- [ ] **Step 1: Write failing CLI validation test**

Update CLI tests to generate a bundle from a run fixture and invoke:

```python
result = CliRunner().invoke(app, ["validate-okf", "--bundle", str(bundle)])
assert result.exit_code == 0
assert "OKF valid" in result.output
```

- [ ] **Step 2: Run CLI validation test to verify failure**

Run: `.venv/bin/pytest tests/test_cli.py::test_validate_okf_command_validates_bundle -q`

Expected: FAIL because the command still exits with the Phase 5 placeholder.

- [ ] **Step 3: Implement CLI validator command**

Call `validate_okf_bundle`, echo concept/link/warning counts, and raise `typer.Exit(1)` on hard errors.

- [ ] **Step 4: Write failing run pipeline manifest test**

Update `test_run_command_creates_phase4_artifacts` to assert Phase 5 output: `Phase 5 complete`, bundle files exist, manifest status is `phase5_complete`, `phase_status.phase5_okf == "complete"`, artifact paths include `okf_bundle`, `okf_manifest`, and `okf_validation_report`, and stage timings include `okf_export` and `okf_validate`.

- [ ] **Step 5: Run run-pipeline test to verify failure**

Run: `.venv/bin/pytest tests/test_cli.py::test_run_command_creates_phase5_artifacts -q`

Expected: FAIL until the pipeline runs OKF export and validation.

- [ ] **Step 6: Implement Phase 5 manifest and pipeline wiring**

Add `build_phase5_manifest`; import exporter and validator; run export after Phase 4; validate to `<run_dir>/okf_validation_report.json`; fail the run on hard validation errors; write final manifest.

- [ ] **Step 7: Run CLI tests**

Run: `.venv/bin/pytest tests/test_cli.py -q`

Expected: PASS.

## Task 4: Status, Smoke Run, And Final Verification

**Files:**
- Modify: `IMPLEMENTATION_STATUS.md`

**Interfaces:**
- Consumes all Phase 5 tasks.
- Produces updated implementation status and verification evidence.

- [ ] **Step 1: Run full tests**

Run: `.venv/bin/pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run Ruff**

Run: `.venv/bin/ruff check .`

Expected: all checks pass.

- [ ] **Step 3: Run Phase 5 smoke commands**

Run: `.venv/bin/python -m fraud_demo generate-data --rows 180 --output /private/tmp/fraud-sentinel-phase5-smoke.csv --seed 42`

Expected: command exits 0 and writes the CSV plus scenario manifest.

Run: `.venv/bin/python -m fraud_demo run --input /private/tmp/fraud-sentinel-phase5-smoke.csv --run-id RUN_PHASE5_SMOKE --artifacts-dir /private/tmp/fraud-sentinel-phase5-artifacts --force`

Expected: command exits 0, prints `Phase 5 complete`, writes `artifacts/okf_bundle`, and writes `okf_validation_report.json`.

Run: `.venv/bin/python -m fraud_demo validate-okf --bundle artifacts/okf_bundle`

Expected: command exits 0 and prints `OKF valid`.

- [ ] **Step 4: Update implementation status**

Record Phase 5 as complete, list assumptions, verification commands, smoke output, and any non-blocking warnings.

- [ ] **Step 5: Publish**

Run final `git status -sb`, inspect diff, commit the Phase 5 branch, push, open a PR, merge to `main`, and verify `main` contains the merged Phase 5 commit and remains clean.
