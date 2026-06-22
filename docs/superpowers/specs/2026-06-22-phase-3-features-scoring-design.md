# Phase 3 Features And Scoring Design

## Summary

Phase 3 adds deterministic account feature engineering, configurable rule scoring, rule evidence records, and alert generation to the Phase 2 pipeline. It consumes `normalized_transactions.parquet` from a run directory and writes:

- `account_features.parquet`
- `account_risk.parquet`
- `rule_evidence.parquet`
- `alerts.parquet`

The outputs identify suspicious indicators that require human review. They do not label accounts as confirmed fraud.

## Requirements

- Follow `PRD.md` Phase 3 and functional requirements FR-006 through FR-010.
- Preserve Phase 2 artifacts and behavior.
- Do not send raw transaction data to external models or APIs.
- Keep scoring deterministic and rule-based.
- Keep rule thresholds and weights configurable through `config/rules.yaml`.
- Mark rules as `not_evaluated` when required evidence is unavailable.
- Store run provenance fields including run ID, source data fingerprint, rules config hash, and creation timestamps.
- Add threshold boundary tests for each baseline rule.
- Update `IMPLEMENTATION_STATUS.md` with assumptions, verification output, and blockers.

## Design Options

### Option A: Pandas-first Phase 3

Use pandas to read Phase 2 Parquet artifacts, compute account-level aggregates, evaluate rules, and write Parquet outputs. Register the resulting frames into the existing run DuckDB database for later phases.

Trade-offs: This matches the current Phase 2 implementation, keeps tests straightforward, and is good enough for the MVP sample sizes. It may need DuckDB rewrites during Phase 8 performance hardening.

### Option B: DuckDB-first Phase 3

Compute feature aggregates directly in SQL against `transactions.duckdb`.

Trade-offs: This is closer to the one-million-row performance target, but it adds more SQL surface before the scoring contract is stable and makes unit tests less direct.

### Option C: Hybrid SQL features with pandas scoring

Use DuckDB SQL for heavy aggregations and pandas for rule evidence and alerts.

Trade-offs: This is a likely future optimization, but it is more complex than Phase 3 needs.

## Decision

Use Option A for Phase 3. The codebase is currently pandas-first, and the PRD prioritizes deterministic, explainable artifacts before performance hardening. The implementation will keep file boundaries clean so Phase 8 can replace selected feature calculations with DuckDB SQL without changing artifact schemas.

## Public Interfaces

`src/fraud_demo/features.py` will expose:

```python
@dataclass(frozen=True)
class FeatureEngineeringResult:
    run_id: str
    run_dir: Path
    account_features_path: Path
    account_count: int
    snapshot_timestamp: str | None

def compute_account_features(
    run_dir: Path | str,
    *,
    short_cycle_max_length: int = 5,
    short_cycle_edge_limit: int = 50_000,
) -> FeatureEngineeringResult:
    ...
```

`src/fraud_demo/scoring.py` will expose:

```python
@dataclass(frozen=True)
class ScoringResult:
    run_id: str
    run_dir: Path
    account_risk_path: Path
    rule_evidence_path: Path
    account_count: int
    evidence_count: int
    rules_config_hash: str

def score_accounts(
    run_dir: Path | str,
    *,
    rules_path: Path | str = "config/rules.yaml",
) -> ScoringResult:
    ...
```

`src/fraud_demo/alerts.py` will expose:

```python
@dataclass(frozen=True)
class AlertGenerationResult:
    run_id: str
    run_dir: Path
    alerts_path: Path
    alert_count: int

def generate_alerts(
    run_dir: Path | str,
    *,
    rules_path: Path | str = "config/rules.yaml",
) -> AlertGenerationResult:
    ...
```

The CLI `run` command will call ingestion, profiling, feature engineering, scoring, and alert generation in sequence.

## Account Feature Schema

Every row in `account_features.parquet` represents one account observed as either sender or receiver in the normalized run.

Required fields:

- `run_id`
- `account_id`
- `snapshot_timestamp`
- `first_activity_at`
- `last_activity_at`
- `incoming_count_24h`
- `outgoing_count_24h`
- `incoming_amount_24h`
- `outgoing_amount_24h`
- `unique_senders_7d`
- `unique_receivers_7d`
- `incoming_amount_7d`
- `outgoing_amount_7d`
- `pass_through_ratio_7d`
- `hold_time_proxy_minutes`
- `cross_border_out_ratio_7d`
- `night_activity_ratio_7d`
- `round_amount_ratio_7d`
- `shared_device_account_count_30d`
- `shared_ip_account_count_30d`
- `account_age_days`
- `active_days_30d`
- `counterparty_concentration_7d`
- `reciprocal_transfer_ratio_7d`
- `short_cycle_flag`

If an optional source field is absent, the related feature is stored as null. If the field exists but no qualifying activity exists, ratio/count features use zero and hold-time uses null.

`hold_time_proxy_minutes` is a proxy. It is computed per account by taking the median daily positive interval, in minutes, between the first inbound transfer and the first later outbound transfer on the same UTC date, limited to intervals less than or equal to 24 hours.

`short_cycle_flag` is computed only when the seven-day unique-edge graph is under the safety cap. If the graph exceeds `short_cycle_edge_limit`, the value is null so the rule becomes `not_evaluated`. This safety cap is not a detection threshold; it protects the MVP from expensive full-graph cycle detection before Phase 4.

## Rule Scoring

The enabled rules in `config/rules.yaml` are evaluated against `account_features.parquet`.

Evaluation statuses:

- `triggered`
- `not_triggered`
- `not_evaluated`

`not_evaluated` contributes zero points. A rule is not evaluated when all evidence required for its predicate is unavailable. `shared_access_point` may evaluate when device evidence or IP evidence is available, because the PRD condition is device OR IP.

Risk scoring:

```text
raw_score = sum(weight for triggered enabled rules)
risk_score = min(raw_score, 100)
```

Severity comes from the configured `severity_bands`.

## Rule Evidence Schema

`rule_evidence.parquet` stores one row per account and enabled rule evaluation.

Required fields:

- `run_id`
- `account_id`
- `rule_id`
- `rule_version`
- `rule_weight`
- `evaluation_status`
- `triggered`
- `feature_values_json`
- `thresholds_json`
- `human_explanation`
- `rules_config_hash`
- `created_at`

Triggered explanations use deterministic text and include the measured feature values and configured thresholds. Missing evidence text states which features were unavailable and does not invent values.

## Account Risk Schema

`account_risk.parquet` stores one row per account.

Required fields:

- `run_id`
- `account_id`
- `snapshot_timestamp`
- `raw_score`
- `risk_score`
- `risk_level`
- `triggered_rule_ids`
- `triggered_rule_count`
- `not_evaluated_rule_ids`
- `rules_config_hash`
- `source_data_fingerprint`
- `created_at`
- selected alert-facing feature fields from the PRD alert schema

The selected alert-facing feature fields are copied from `account_features.parquet` to keep the dashboard and OKF phases from rereading raw transactions for common views.

## Alert Schema

`alerts.parquet` includes only accounts that meet the configured alert criteria:

- `risk_score >= alert_min_score`; or
- at least one configured mandatory rule triggers.

Phase 3 does not implement suspicious-cluster alerting because clusters start in Phase 4.

Required fields:

- `alert_id`
- `run_id`
- `account_id`
- `risk_score`
- `risk_level`
- `alert_status`
- `triggered_rule_ids`
- `triggered_rule_count`
- `explanation`
- `first_activity_at`
- `last_activity_at`
- `incoming_amount_7d`
- `outgoing_amount_7d`
- `unique_senders_7d`
- `unique_receivers_7d`
- `hold_time_proxy_minutes`
- `cluster_id`
- `source_data_fingerprint`
- `rules_config_hash`
- `created_at`
- `okf_concept_id`

`alert_id` uses the stable PRD format `ALERT_<run_id>_<account_id>` for Phase 3. Later privacy work may replace `account_id` with a masked identifier if required by the user.

Alert explanations must include the phrase "requires human review" and must not call the account confirmed fraud.

## Manifest Updates

The run manifest written by `run` will change from `phase2_complete` to `phase3_complete` after alerts are generated. It will add artifact paths for `account_features`, `account_risk`, `rule_evidence`, and `alerts`, set `rules_config_hash`, update `alert_count`, and mark `phase3_features_scoring` complete.

Stage timings will include `feature_engineering`, `scoring`, and `alert_generation`. Existing Phase 2 timing fields may remain absent until a future pipeline timing pass, but Phase 3 stage durations must be recorded for new runs.

## Testing

The TDD suite will add:

- `tests/test_features.py` for feature windows, hold-time proxy, shared device/IP counts, optional missing field behavior, and short-cycle flag behavior.
- `tests/test_scoring.py` for every baseline rule below, at, and above threshold; severity bands; capped score; unavailable evidence; and rules config hash.
- `tests/test_alerts.py` for threshold-based alerts, stable IDs, human-review language, and Parquet schema.
- CLI coverage that verifies `run` writes all Phase 3 artifacts and reports Phase 3 completion.

## Self Review

- Placeholder scan: No TBD or TODO items remain.
- Consistency check: Public interfaces, artifact names, and schemas match the PRD and Phase 2 run directory layout.
- Scope check: Phase 3 is limited to features, scoring, evidence, risk, alerts, manifest updates, tests, and status docs. Graphs, clusters, OKF export, dashboard details, and monitoring remain later phases.
- Ambiguity resolution: Short-cycle scoring is bounded and nullable in Phase 3, with full graph-cycle handling deferred to Phase 4.
