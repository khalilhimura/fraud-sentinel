"""Deterministic rule-based account scoring for Phase 3."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from fraud_demo.config import RuleDefinition, canonical_yaml_hash, load_rules_config

TRIGGERED = "triggered"
NOT_TRIGGERED = "not_triggered"
NOT_EVALUATED = "not_evaluated"

ALERT_FEATURE_COLUMNS = [
    "snapshot_timestamp",
    "first_activity_at",
    "last_activity_at",
    "incoming_amount_7d",
    "outgoing_amount_7d",
    "unique_senders_7d",
    "unique_receivers_7d",
    "hold_time_proxy_minutes",
]


@dataclass(frozen=True)
class ScoringResult:
    """Artifacts and counts from rule scoring."""

    run_id: str
    run_dir: Path
    account_risk_path: Path
    rule_evidence_path: Path
    account_count: int
    evidence_count: int
    rules_config_hash: str


@dataclass(frozen=True)
class RuleOutcome:
    """One rule evaluation outcome for one account."""

    status: str
    triggered: bool
    feature_values: dict[str, object]
    explanation: str


def _json_value(value: Any) -> object:
    if _is_missing(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _number(value: Any) -> float:
    return float(value)


def _bool_value(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return bool(value)


def _feature_values(row: pd.Series, fields: list[str]) -> dict[str, object]:
    return {field: _json_value(row.get(field)) for field in fields}


def _thresholds(rule: RuleDefinition) -> dict[str, object]:
    return {key: _json_value(value) for key, value in rule.thresholds.items()}


def _missing_features(row: pd.Series, fields: list[str]) -> list[str]:
    return [field for field in fields if field not in row.index or _is_missing(row.get(field))]


def _not_evaluated(
    rule_id: str,
    rule: RuleDefinition,
    row: pd.Series,
    missing: list[str],
) -> RuleOutcome:
    return RuleOutcome(
        status=NOT_EVALUATED,
        triggered=False,
        feature_values=_feature_values(row, rule.required_features),
        explanation=(
            f"{rule_id} was not evaluated because required feature(s) "
            f"{', '.join(missing)} were unavailable."
        ),
    )


def _outcome(
    rule_id: str,
    rule: RuleDefinition,
    row: pd.Series,
    triggered: bool,
    detail: str,
) -> RuleOutcome:
    return RuleOutcome(
        status=TRIGGERED if triggered else NOT_TRIGGERED,
        triggered=triggered,
        feature_values=_feature_values(row, rule.required_features),
        explanation=(
            f"{rule_id} triggered because {detail}."
            if triggered
            else f"{rule_id} did not trigger because {detail}."
        ),
    )


def _evaluate_high_fan_in(rule_id: str, rule: RuleDefinition, row: pd.Series) -> RuleOutcome:
    missing = _missing_features(row, rule.required_features)
    if missing:
        return _not_evaluated(rule_id, rule, row, missing)
    value = _number(row["unique_senders_7d"])
    threshold = _number(rule.thresholds["unique_senders_7d"])
    return _outcome(
        rule_id,
        rule,
        row,
        value >= threshold,
        f"unique_senders_7d={value:g} and threshold={threshold:g}",
    )


def _evaluate_rapid_pass_through(rule_id: str, rule: RuleDefinition, row: pd.Series) -> RuleOutcome:
    missing = _missing_features(row, rule.required_features)
    if missing:
        return _not_evaluated(rule_id, rule, row, missing)
    ratio = _number(row["pass_through_ratio_7d"])
    hold_minutes = _number(row["hold_time_proxy_minutes"])
    ratio_threshold = _number(rule.thresholds["pass_through_ratio_7d"])
    hold_threshold = _number(rule.thresholds["hold_time_proxy_minutes_max"])
    triggered = ratio >= ratio_threshold and hold_minutes <= hold_threshold
    return _outcome(
        rule_id,
        rule,
        row,
        triggered,
        (
            f"pass_through_ratio_7d={ratio:g} with threshold={ratio_threshold:g}, "
            f"hold_time_proxy_minutes={hold_minutes:g} with maximum={hold_threshold:g}"
        ),
    )


def _evaluate_high_velocity(rule_id: str, rule: RuleDefinition, row: pd.Series) -> RuleOutcome:
    missing = _missing_features(row, rule.required_features)
    if missing:
        return _not_evaluated(rule_id, rule, row, missing)
    total = _number(row["incoming_count_24h"]) + _number(row["outgoing_count_24h"])
    threshold = _number(rule.thresholds["total_count_24h"])
    return _outcome(
        rule_id,
        rule,
        row,
        total >= threshold,
        f"total_count_24h={total:g} and threshold={threshold:g}",
    )


def _evaluate_high_fan_out(rule_id: str, rule: RuleDefinition, row: pd.Series) -> RuleOutcome:
    missing = _missing_features(row, rule.required_features)
    if missing:
        return _not_evaluated(rule_id, rule, row, missing)
    value = _number(row["unique_receivers_7d"])
    threshold = _number(rule.thresholds["unique_receivers_7d"])
    return _outcome(
        rule_id,
        rule,
        row,
        value >= threshold,
        f"unique_receivers_7d={value:g} and threshold={threshold:g}",
    )


def _evaluate_shared_access_point(
    rule_id: str,
    rule: RuleDefinition,
    row: pd.Series,
) -> RuleOutcome:
    device_value = row.get("shared_device_account_count_30d")
    ip_value = row.get("shared_ip_account_count_30d")
    if _is_missing(device_value) and _is_missing(ip_value):
        return _not_evaluated(rule_id, rule, row, rule.required_features)
    available_values = [
        _number(value) for value in [device_value, ip_value] if not _is_missing(value)
    ]
    observed = max(available_values)
    threshold = _number(rule.thresholds["shared_accounts"])
    return _outcome(
        rule_id,
        rule,
        row,
        observed >= threshold,
        f"shared account count={observed:g} and threshold={threshold:g}",
    )


def _evaluate_cross_border_funnel(
    rule_id: str,
    rule: RuleDefinition,
    row: pd.Series,
) -> RuleOutcome:
    missing = _missing_features(row, rule.required_features)
    if missing:
        return _not_evaluated(rule_id, rule, row, missing)
    incoming = _number(row["incoming_amount_7d"])
    ratio = _number(row["cross_border_out_ratio_7d"])
    incoming_threshold = _number(rule.thresholds["incoming_amount_7d"])
    ratio_threshold = _number(rule.thresholds["cross_border_out_ratio_7d"])
    triggered = incoming >= incoming_threshold and ratio >= ratio_threshold
    return _outcome(
        rule_id,
        rule,
        row,
        triggered,
        (
            f"incoming_amount_7d={incoming:g} with threshold={incoming_threshold:g}, "
            f"cross_border_out_ratio_7d={ratio:g} with threshold={ratio_threshold:g}"
        ),
    )


def _evaluate_new_account_burst(rule_id: str, rule: RuleDefinition, row: pd.Series) -> RuleOutcome:
    missing = _missing_features(row, rule.required_features)
    if missing:
        return _not_evaluated(rule_id, rule, row, missing)
    age = _number(row["account_age_days"])
    total = _number(row["incoming_count_24h"]) + _number(row["outgoing_count_24h"])
    age_threshold = _number(rule.thresholds["account_age_days_max"])
    count_threshold = _number(rule.thresholds["total_count_24h"])
    triggered = age <= age_threshold and total >= count_threshold
    return _outcome(
        rule_id,
        rule,
        row,
        triggered,
        (
            f"account_age_days={age:g} with maximum={age_threshold:g}, "
            f"total_count_24h={total:g} with threshold={count_threshold:g}"
        ),
    )


def _evaluate_short_cycle(rule_id: str, rule: RuleDefinition, row: pd.Series) -> RuleOutcome:
    missing = _missing_features(row, rule.required_features)
    if missing:
        return _not_evaluated(rule_id, rule, row, missing)
    triggered = _bool_value(row["short_cycle_flag"])
    return _outcome(rule_id, rule, row, triggered, f"short_cycle_flag={triggered}")


EVALUATORS = {
    "high_fan_in": _evaluate_high_fan_in,
    "rapid_pass_through": _evaluate_rapid_pass_through,
    "high_velocity": _evaluate_high_velocity,
    "high_fan_out": _evaluate_high_fan_out,
    "shared_access_point": _evaluate_shared_access_point,
    "cross_border_funnel": _evaluate_cross_border_funnel,
    "new_account_burst": _evaluate_new_account_burst,
    "short_cycle": _evaluate_short_cycle,
}


def risk_level_for_score(score: int, severity_bands: Mapping[str, tuple[int, int]]) -> str:
    """Return the configured severity label for a score."""

    for level, bounds in severity_bands.items():
        lower, upper = bounds
        if lower <= score <= upper:
            return level.replace("_", " ").title()
    return "Critical" if score > 100 else "Low"


def _source_data_fingerprint(run_path: Path) -> str | None:
    manifest_path = run_path / "run_manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    value = manifest.get("source_data_fingerprint")
    return str(value) if value is not None else None


def _evaluate_rules(
    features: pd.DataFrame,
    *,
    rules_path: Path | str,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    config = load_rules_config(rules_path)
    rules_config_hash = canonical_yaml_hash(rules_path)
    created_at = datetime.now(UTC).isoformat()
    evidence_records: list[dict[str, object]] = []
    risk_records: list[dict[str, object]] = []

    for row in features.to_dict(orient="records"):
        feature_row = pd.Series(row)
        triggered_rule_ids: list[str] = []
        not_evaluated_rule_ids: list[str] = []
        raw_score = 0
        for rule_id, rule in config.rules.items():
            if not rule.enabled:
                continue
            evaluator = EVALUATORS.get(rule_id)
            if evaluator is None:
                outcome = RuleOutcome(
                    status=NOT_EVALUATED,
                    triggered=False,
                    feature_values=_feature_values(feature_row, rule.required_features),
                    explanation=f"{rule_id} was not evaluated because no evaluator is implemented.",
                )
            else:
                outcome = evaluator(rule_id, rule, feature_row)
            if outcome.triggered:
                triggered_rule_ids.append(rule_id)
                raw_score += rule.weight
            if outcome.status == NOT_EVALUATED:
                not_evaluated_rule_ids.append(rule_id)
            evidence_records.append(
                {
                    "run_id": feature_row["run_id"],
                    "account_id": feature_row["account_id"],
                    "rule_id": rule_id,
                    "rule_version": config.version,
                    "rule_weight": int(rule.weight),
                    "evaluation_status": outcome.status,
                    "triggered": bool(outcome.triggered),
                    "feature_values_json": json.dumps(
                        outcome.feature_values,
                        sort_keys=True,
                    ),
                    "thresholds_json": json.dumps(_thresholds(rule), sort_keys=True),
                    "human_explanation": outcome.explanation,
                    "rules_config_hash": rules_config_hash,
                    "created_at": created_at,
                }
            )

        risk_score = min(raw_score, 100)
        risk_record = {
            "run_id": feature_row["run_id"],
            "account_id": feature_row["account_id"],
            "snapshot_timestamp": feature_row.get("snapshot_timestamp"),
            "raw_score": int(raw_score),
            "risk_score": int(risk_score),
            "risk_level": risk_level_for_score(int(risk_score), config.severity_bands),
            "triggered_rule_ids": triggered_rule_ids,
            "triggered_rule_count": len(triggered_rule_ids),
            "not_evaluated_rule_ids": not_evaluated_rule_ids,
            "rules_config_hash": rules_config_hash,
            "created_at": created_at,
        }
        for column in ALERT_FEATURE_COLUMNS:
            if column in feature_row:
                risk_record[column] = _json_value(feature_row[column])
        risk_records.append(risk_record)

    return pd.DataFrame(risk_records), pd.DataFrame(evidence_records), rules_config_hash


def _write_scoring_tables(
    run_path: Path,
    risk: pd.DataFrame,
    evidence: pd.DataFrame,
) -> tuple[Path, Path]:
    account_risk_path = run_path / "account_risk.parquet"
    rule_evidence_path = run_path / "rule_evidence.parquet"
    risk.to_parquet(account_risk_path, index=False)
    evidence.to_parquet(rule_evidence_path, index=False)
    duckdb_path = run_path / "transactions.duckdb"
    with duckdb.connect(str(duckdb_path)) as connection:
        connection.register("account_risk_df", risk)
        connection.register("rule_evidence_df", evidence)
        connection.execute("create or replace table account_risk as select * from account_risk_df")
        connection.execute(
            "create or replace table rule_evidence as select * from rule_evidence_df"
        )
        connection.unregister("account_risk_df")
        connection.unregister("rule_evidence_df")
    return account_risk_path, rule_evidence_path


def score_accounts(
    run_dir: Path | str,
    *,
    rules_path: Path | str = "config/rules.yaml",
) -> ScoringResult:
    """Evaluate configured deterministic rules for all account features in a run."""

    run_path = Path(run_dir)
    features = pd.read_parquet(run_path / "account_features.parquet")
    risk, evidence, rules_config_hash = _evaluate_rules(features, rules_path=rules_path)
    risk["source_data_fingerprint"] = _source_data_fingerprint(run_path)
    account_risk_path, rule_evidence_path = _write_scoring_tables(run_path, risk, evidence)
    return ScoringResult(
        run_id=run_path.name,
        run_dir=run_path,
        account_risk_path=account_risk_path,
        rule_evidence_path=rule_evidence_path,
        account_count=int(len(risk)),
        evidence_count=int(len(evidence)),
        rules_config_hash=rules_config_hash,
    )
