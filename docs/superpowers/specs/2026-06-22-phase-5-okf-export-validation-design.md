# Phase 5 OKF Export And Validation Design

## Summary

Phase 5 turns the completed Phase 4 analytical artifacts into an OKF v0.1
Markdown bundle and validates it. The exporter consumes run artifacts only; it
does not read raw CSV files, does not call external services, and does not write
one Markdown file per transaction.

The generated bundle is written to `artifacts/okf_bundle/` by default and can be
opened directly as an Obsidian vault. The exact source run remains recorded in
the run manifest and bundle manifests.

## Requirements

- Follow `PRD.md` Phase 5, FR-014 through FR-019, FR-027, FR-028, and
  AGENTS.md.
- Consume Phase 4 run artifacts:
  `account_risk.parquet`, `alerts.parquet`, `rule_evidence.parquet`,
  `graph_nodes.parquet`, `graph_edges.parquet`, `clusters.parquet`, and
  `run_manifest.json`.
- Use `config/okf.yaml` for output directory, OKF version, link style, export
  limits, privacy flags, and concept type labels.
- Use Jinja2 templates under `src/fraud_demo/templates/`.
- Generate root `index.md`, `log.md`, subdirectory `index.md` files, and concept
  files for accounts, alerts, clusters, signals, the run, the dataset, and the
  mule-account runbook.
- Use standard relative Markdown links, not Wikilinks.
- Include typed relation frontmatter when configured, while keeping equivalent
  Markdown links in each body.
- Ensure every non-reserved concept has parseable YAML frontmatter with a
  non-empty `type`.
- Label every account, alert, and cluster as suspicious indicators requiring
  human review, not confirmed fraud.
- Exclude raw transaction descriptions, customer PII, and raw transaction-note
  files from the OKF bundle.
- Respect all configured export limits.
- Update `okf_concept_id` in exported `account_risk.parquet` rows and
  `alerts.parquet` rows as the clean downstream dashboard contract.
- Write `okf_manifest.json` at bundle root and
  `okf_validation_report.json` in the source run directory.
- Register OKF artifact paths, `okf_export` timing, `okf_validate` timing,
  `status = phase5_complete`, and `phase_status.phase5_okf = complete` in the
  run manifest.
- Wire `python -m fraud_demo validate-okf --bundle artifacts/okf_bundle`.
- Wire the full `run` pipeline through OKF export and validation.

## Design Options

### Option A: Run-owned deterministic exporter

The exporter reads one completed Phase 4 run directory, renders bounded concepts,
updates the run artifacts with concept IDs, validates the bundle, and extends the
same run manifest.

Trade-offs: This keeps provenance simple and matches the current pipeline. It
does mean the canonical bundle is rewritten on each run, with run history
preserved in concept content and `log.md`.

### Option B: Independent OKF command only

The exporter is a standalone command that validates any arbitrary artifact set
but is not part of the full pipeline.

Trade-offs: This is easier to isolate, but it fails the Phase 5 requirement that
`run` produce and validate the OKF bundle and register artifact paths.

### Option C: One concept per analytical row

The exporter creates Markdown for every account risk row and every edge.

Trade-offs: This is simple to map, but it violates export-limit and scale-aware
requirements and would make the vault noisy.

## Decision

Use Option A. Phase 5 exports a bounded, run-owned OKF bundle from Phase 4
artifacts, validates it immediately, and records the result in the run manifest.
The exporter will not create raw transaction concepts. It will select accounts,
alerts, clusters, and graph context according to `config/okf.yaml`.

## Bundle Structure

The exporter creates the PRD hierarchy:

```text
artifacts/okf_bundle/
  index.md
  log.md
  okf_manifest.json
  accounts/index.md
  accounts/<account_id>.md
  alerts/index.md
  alerts/<alert_id>.md
  clusters/index.md
  clusters/<cluster_id>.md
  signals/index.md
  signals/<rule_id>.md
  devices/index.md
  ips/index.md
  metrics/index.md
  runs/index.md
  runs/<run_id>.md
  datasets/index.md
  datasets/transactions.md
  runbooks/index.md
  runbooks/mule_account_investigation.md
  references/index.md
```

Only the listed concept types are required in Phase 5. Empty optional
directories still receive `index.md` so the bundle navigation is complete.

## Concept Selection

Accounts are selected in this order:

1. Accounts attached to exported alerts.
2. High and Critical accounts in `account_risk.parquet`.
3. Accounts present in `graph_nodes.parquet`, sorted by suspicious flag, risk
   score, context flag, and account ID.

Selection stops at `export_limits.max_accounts`. Alerts and clusters are sorted
by risk and deterministic IDs and capped by `max_alerts` and `max_clusters`.
Signal concepts are generated from enabled rules in `config/rules.yaml`.

## Concept IDs And Links

Concept IDs are bundle-relative paths without `.md`, for example
`accounts/ACC090001` and `alerts/ALERT_RUN_ACC090001`. Filenames are sanitized to
avoid reserved names, path traversal, spaces, and characters that require
consumer-specific behavior.

Markdown links are standard relative links. Templates receive resolved link
targets such as `../signals/high_fan_in.md` or `ACC090001.md`; they do not build
links manually.

When `include_typed_relations_extension` is true, concept frontmatter includes a
`relations` list. This extension mirrors body links and is never the only graph
representation.

## Privacy And Safety

The exporter renders aggregate values, rule evidence, selected transaction IDs
already present in bounded graph edge attributes, and provenance metadata. It
does not render free-text transaction descriptions, customer names, email
addresses, phone numbers, street addresses, or one Markdown file per raw
transaction.

Account, alert, and cluster bodies all include language that the output is a
suspicious indicator requiring human review and is not a confirmed fraud
judgment.

## Public Interfaces

`src/fraud_demo/okf_exporter.py` exposes:

```python
@dataclass(frozen=True)
class OkfExportResult:
    run_id: str
    run_dir: Path
    bundle_path: Path
    okf_manifest_path: Path
    concept_count: int
    account_count: int
    alert_count: int
    cluster_count: int

def export_okf_bundle(
    run_dir: Path | str,
    *,
    okf_config_path: Path | str = "config/okf.yaml",
    rules_path: Path | str = "config/rules.yaml",
) -> OkfExportResult:
    ...
```

`src/fraud_demo/okf_validator.py` exposes:

```python
@dataclass(frozen=True)
class OkfValidationResult:
    okf_version: str
    bundle_path: Path
    valid: bool
    concept_count: int
    link_count: int
    hard_errors: list[dict[str, str]]
    warnings: list[dict[str, str]]
    report_path: Path | None

def validate_okf_bundle(
    bundle: Path | str,
    *,
    report_path: Path | str | None = None,
    max_file_size_bytes: int = 512_000,
) -> OkfValidationResult:
    ...
```

`src/fraud_demo/manifests.py` adds:

```python
def build_phase5_manifest(
    phase4_manifest: dict[str, Any],
    export_result: Any,
    validation_result: Any,
    stage_timings_seconds: dict[str, float],
) -> dict[str, Any]:
    ...
```

The CLI `run` command calls export, validation, and final manifest writing after
Phase 4. The CLI `validate-okf` command validates an existing bundle and exits
non-zero on hard errors.

## Validation Rules

Hard errors:

- Non-reserved Markdown file lacks YAML frontmatter.
- YAML frontmatter cannot be parsed.
- Concept frontmatter lacks a non-empty `type`.
- Duplicate concept ID.
- Markdown file is not valid UTF-8.
- Reserved `index.md` or `log.md` has concept-style frontmatter where it should
  not.
- A discovered Markdown path escapes the bundle root.

Warnings:

- Recommended fields such as `title` or `description` are missing.
- Timestamp is not ISO 8601.
- Generated internal Markdown link is broken.
- Typed relation target does not exist.
- Concept file exceeds the configured size limit.
- Privacy scanner detects disallowed field names or common PII patterns.
- Directory lacks `index.md`.

The validator writes the PRD report schema and treats broken links as warnings,
not hard errors.

## Testing

Use TDD for each behavior. Tests cover:

- Frontmatter generation.
- Relative Markdown links and absence of Wikilinks.
- Bundle hierarchy, root index, subdirectory indexes, and log.
- Jinja escaping of body text.
- Export limits.
- Privacy exclusions and no raw transaction notes.
- Reserved filename handling.
- Broken-link warnings.
- Hard validation errors.
- Validation report schema.
- CLI `validate-okf` behavior.
- Full `run` manifest updates, Phase 5 status, artifact paths, and stage
  timings.

## Out Of Scope

- Dashboard pages.
- Monitoring rerun logic.
- Runtime LLM narratives.
- Full device, IP, and metric concept generation beyond directory indexes.
- Obsidian automation. Phase 5 writes compatible files and documents the smoke
  path through generated indexes and status notes.
