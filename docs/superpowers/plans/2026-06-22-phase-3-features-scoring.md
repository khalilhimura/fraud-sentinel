# Phase 3 Features And Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Phase 3 account feature engineering, configurable rule scoring, rule evidence records, account risk artifacts, and alert artifacts.

**Architecture:** Reuse Phase 2 run directories as the boundary. `features.py` reads normalized transactions and writes `account_features.parquet`; `scoring.py` reads account features and rules config and writes `account_risk.parquet` plus `rule_evidence.parquet`; `alerts.py` reads account risk and evidence and writes `alerts.parquet`; `cli.py` wires the stages and manifest updates.

**Tech Stack:** Python 3.12+, pandas, pyarrow, DuckDB, Pydantic, Typer, pytest, Ruff.

## Global Constraints

- Treat `PRD.md` as the source of truth.
- Do not send raw transaction data to a runtime LLM or external API.
- Keep detection deterministic and rule-based.
- Use synthetic or approved anonymized data only.
- Label outputs as suspicious indicators requiring human review, not confirmed fraud.
- Keep thresholds and weights configurable in `config/rules.yaml`.
- Preserve run provenance, source fingerprints, rules config hashes, source row lineage, and stage timings.
- Do not generate one Markdown file per raw transaction.
- Do not weaken or delete valid tests just to make the suite pass.

---

## File Structure

- Modify `src/fraud_demo/features.py`: account-level feature calculations and Parquet/DuckDB materialization.
- Modify `src/fraud_demo/scoring.py`: rule evaluation, evidence records, severity bands, risk scoring, and Parquet/DuckDB materialization.
- Modify `src/fraud_demo/alerts.py`: alert filtering, alert IDs, human-review explanations, and Parquet/DuckDB materialization.
- Modify `src/fraud_demo/config.py`: optional `mandatory` field on rule definitions.
- Modify `src/fraud_demo/manifests.py`: Phase 3 manifest builder or updater.
- Modify `src/fraud_demo/cli.py`: run command orchestration and Phase 3 output text.
- Create `tests/test_features.py`: deterministic feature tests.
- Create `tests/test_scoring.py`: rule boundary and evidence tests.
- Create `tests/test_alerts.py`: alert artifact tests.
- Modify `tests/test_cli.py`: Phase 3 CLI smoke coverage.
- Modify `IMPLEMENTATION_STATUS.md`: Phase tracker, assumptions, and verification evidence.

## Task 1: Account Feature Engineering

**Files:**
- Modify: `src/fraud_demo/features.py`
- Test: `tests/test_features.py`

**Interfaces:**
- Produces: `FeatureEngineeringResult`
- Produces: `compute_account_features(run_dir: Path | str, *, short_cycle_max_length: int = 5, short_cycle_edge_limit: int = 50_000) -> FeatureEngineeringResult`

- [ ] **Step 1: Write failing feature tests**

Create `tests/test_features.py` with a helper that writes `normalized_transactions.parquet` into `tmp_path / "artifacts" / "runs" / "RUN_FEATURES"`. Include transactions where `ACC_MULE` has 10 unique senders in seven days, one inbound followed by outbound within 60 minutes, cross-border outbound activity, shared device/IP senders, a new account opening date, reciprocal counterparties, and a three-account cycle.

Assert:

```python
result = compute_account_features(run_dir)
features = pd.read_parquet(result.account_features_path).set_index("account_id")

assert result.run_id == "RUN_FEATURES"
assert result.account_count >= 1
assert features.loc["ACC_MULE", "unique_senders_7d"] == 10
assert features.loc["ACC_MULE", "incoming_count_24h"] == 10
assert features.loc["ACC_MULE", "outgoing_count_24h"] == 1
assert features.loc["ACC_MULE", "pass_through_ratio_7d"] >= 0.8
assert features.loc["ACC_MULE", "hold_time_proxy_minutes"] == 60
assert features.loc["ACC_MULE", "cross_border_out_ratio_7d"] == 1.0
assert features.loc["ACC_NEW", "account_age_days"] == 5
assert bool(features.loc["ACC_CYCLE_A", "short_cycle_flag"]) is True
```

Add a second test with optional columns omitted and assert optional-derived fields are null rather than invented.

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/test_features.py -q`

Expected: FAIL because `compute_account_features` still raises the Phase 3 placeholder error.

- [ ] **Step 3: Implement minimal feature calculation**

Implement the dataclass, helper functions for window filtering, account universe creation, inbound/outbound aggregations, hold-time proxy, optional-column derived features, bounded short-cycle flags, Parquet writing, and DuckDB table registration.

The implementation must write `account_features.parquet` with the schema named in the design spec.

- [ ] **Step 4: Run feature tests to verify pass**

Run: `.venv/bin/pytest tests/test_features.py -q`

Expected: PASS.

## Task 2: Configurable Rule Scoring And Evidence

**Files:**
- Modify: `src/fraud_demo/config.py`
- Modify: `src/fraud_demo/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Produces: `ScoringResult`
- Produces: `score_accounts(run_dir: Path | str, *, rules_path: Path | str = "config/rules.yaml") -> ScoringResult`
- Produces: `risk_level_for_score(score: int, severity_bands: Mapping[str, tuple[int, int]]) -> str`

- [ ] **Step 1: Write failing scoring tests**

Create `tests/test_scoring.py` with an `account_features.parquet` fixture containing one account below every rule threshold, one account exactly at each threshold, one account above each threshold, one account with unavailable optional features, and one account whose triggered rule weights exceed 100.

Assert:

```python
result = score_accounts(run_dir)
risk = pd.read_parquet(result.account_risk_path).set_index("account_id")
evidence = pd.read_parquet(result.rule_evidence_path)

assert risk.loc["ACC_AT_THRESHOLD", "risk_score"] >= 50
assert risk.loc["ACC_CAPPED", "risk_score"] == 100
assert risk.loc["ACC_AT_THRESHOLD", "risk_level"] == "High"
assert "rapid_pass_through" in risk.loc["ACC_AT_THRESHOLD", "triggered_rule_ids"]
assert len(result.rules_config_hash) == 64
assert set(evidence["evaluation_status"]) >= {"triggered", "not_triggered", "not_evaluated"}
assert evidence.loc[evidence["rule_id"].eq("rapid_pass_through"), "thresholds_json"].str.contains("0.8").any()
```

Also assert that `risk_level_for_score(24, bands) == "Low"`, `25 == "Medium"`, `50 == "High"`, and `75 == "Critical"`.

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/test_scoring.py -q`

Expected: FAIL because `score_accounts` still raises the Phase 3 placeholder error.

- [ ] **Step 3: Implement scoring and evidence**

Add `mandatory: bool = False` to `RuleDefinition`. Implement per-rule predicate functions for all baseline rules, missing-evidence handling, deterministic explanations, risk score capping, severity lookup, Parquet writes, and DuckDB table registration.

- [ ] **Step 4: Run scoring tests to verify pass**

Run: `.venv/bin/pytest tests/test_scoring.py -q`

Expected: PASS.

## Task 3: Alert Generation

**Files:**
- Modify: `src/fraud_demo/alerts.py`
- Test: `tests/test_alerts.py`

**Interfaces:**
- Produces: `AlertGenerationResult`
- Produces: `generate_alerts(run_dir: Path | str, *, rules_path: Path | str = "config/rules.yaml") -> AlertGenerationResult`

- [ ] **Step 1: Write failing alert tests**

Create `tests/test_alerts.py` with `account_risk.parquet`, `rule_evidence.parquet`, and `run_manifest.json` fixtures. Include one high-risk account, one medium-risk account below the alert threshold, and triggered evidence for the high-risk account.

Assert:

```python
result = generate_alerts(run_dir)
alerts = pd.read_parquet(result.alerts_path)

assert result.alert_count == 1
assert alerts.loc[0, "alert_id"] == "ALERT_RUN_ALERTS_ACC_HIGH"
assert alerts.loc[0, "alert_status"] == "new"
assert alerts.loc[0, "okf_concept_id"] == "alerts/ALERT_RUN_ALERTS_ACC_HIGH"
assert "requires human review" in alerts.loc[0, "explanation"]
assert "confirmed fraud" not in alerts.loc[0, "explanation"].lower()
assert alerts.loc[0, "rules_config_hash"] == "a" * 64
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/test_alerts.py -q`

Expected: FAIL because `generate_alerts` still raises the Phase 3 placeholder error.

- [ ] **Step 3: Implement alert generation**

Load risk and evidence artifacts, filter by `alert_min_score` and mandatory triggered rules, build stable alert IDs, copy PRD alert fields, include deterministic human-review explanations, write `alerts.parquet`, and register the DuckDB table.

- [ ] **Step 4: Run alert tests to verify pass**

Run: `.venv/bin/pytest tests/test_alerts.py -q`

Expected: PASS.

## Task 4: CLI And Manifest Integration

**Files:**
- Modify: `src/fraud_demo/cli.py`
- Modify: `src/fraud_demo/manifests.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `compute_account_features`, `score_accounts`, `generate_alerts`.
- Produces: a `run` command that completes Phase 3 and writes manifest paths for all Phase 3 artifacts.

- [ ] **Step 1: Write failing CLI test update**

Modify `test_run_command_creates_phase2_artifacts` into `test_run_command_creates_phase3_artifacts`. Assert the command output contains `Phase 3 complete`, the four Phase 3 Parquet artifacts exist, and the manifest has `status == "phase3_complete"` plus `phase_status["phase3_features_scoring"] == "complete"`.

- [ ] **Step 2: Run CLI tests to verify failure**

Run: `.venv/bin/pytest tests/test_cli.py -q`

Expected: FAIL because the run command still stops at Phase 2.

- [ ] **Step 3: Implement CLI and manifest update**

Add a Phase 3 manifest helper or updater that records artifact paths, `rules_config_hash`, `alert_count`, `stage_timings_seconds.feature_engineering`, `stage_timings_seconds.scoring`, `stage_timings_seconds.alert_generation`, and `phase3_features_scoring: complete`.

Update `run_pipeline` to call Phase 3 stages after profiling and write a Phase 3 manifest.

- [ ] **Step 4: Run CLI tests to verify pass**

Run: `.venv/bin/pytest tests/test_cli.py -q`

Expected: PASS.

## Task 5: Status, Smoke Run, And Final Verification

**Files:**
- Modify: `IMPLEMENTATION_STATUS.md`

**Interfaces:**
- Consumes all Phase 3 tasks.
- Produces updated implementation status and verification evidence.

- [ ] **Step 1: Run full tests**

Run: `.venv/bin/pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run ruff**

Run: `.venv/bin/ruff check .`

Expected: all checks pass.

- [ ] **Step 3: Run Phase 3 smoke command**

Run: `.venv/bin/python -m fraud_demo generate-data --rows 120 --output /private/tmp/fraud-sentinel-phase3-smoke.csv --seed 42`

Expected: command exits 0 and writes the CSV plus scenario manifest.

Run: `.venv/bin/python -m fraud_demo run --input /private/tmp/fraud-sentinel-phase3-smoke.csv --run-id RUN_PHASE3_SMOKE --artifacts-dir /private/tmp/fraud-sentinel-phase3-artifacts --force`

Expected: command exits 0, prints `Phase 3 complete`, and writes Phase 3 artifacts.

- [ ] **Step 4: Update implementation status**

Record Phase 3 as complete, list assumptions, verification commands, and any non-blocking warnings.

- [ ] **Step 5: Commit and push**

Run:

```bash
git status --short
git add docs/superpowers/specs/2026-06-22-phase-3-features-scoring-design.md docs/superpowers/plans/2026-06-22-phase-3-features-scoring.md src/fraud_demo/features.py src/fraud_demo/scoring.py src/fraud_demo/alerts.py src/fraud_demo/config.py src/fraud_demo/manifests.py src/fraud_demo/cli.py tests/test_features.py tests/test_scoring.py tests/test_alerts.py tests/test_cli.py IMPLEMENTATION_STATUS.md
git commit -m "feat: implement phase 3 scoring artifacts"
git push -u origin codex/phase-3-features-scoring
```

Expected: branch is pushed and ready for merge.

## Self-Review

- Spec coverage: Tasks cover account features, configurable rules, evidence records, risk scoring, alerts, CLI, manifest, docs, and verification.
- Placeholder scan: No TBD, TODO, or deferred implementation placeholder remains inside Phase 3 scope.
- Type consistency: Function names and dataclass names match the design spec and planned tests.
