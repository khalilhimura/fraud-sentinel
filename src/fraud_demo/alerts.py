"""Explainable alert generation for Phase 3."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from fraud_demo.config import load_rules_config

ALERT_COLUMNS = [
    "alert_id",
    "run_id",
    "account_id",
    "risk_score",
    "risk_level",
    "alert_status",
    "triggered_rule_ids",
    "triggered_rule_count",
    "explanation",
    "first_activity_at",
    "last_activity_at",
    "incoming_amount_7d",
    "outgoing_amount_7d",
    "unique_senders_7d",
    "unique_receivers_7d",
    "hold_time_proxy_minutes",
    "cluster_id",
    "source_data_fingerprint",
    "rules_config_hash",
    "created_at",
    "okf_concept_id",
]


@dataclass(frozen=True)
class AlertGenerationResult:
    """Artifacts and counts from alert generation."""

    run_id: str
    run_dir: Path
    alerts_path: Path
    alert_count: int


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if hasattr(value, "tolist"):
        return [str(item) for item in value.tolist()]
    if pd.isna(value):
        return []
    return [str(value)]


def _triggered_explanations(evidence: pd.DataFrame, account_id: str) -> list[str]:
    if evidence.empty:
        return []
    rows = evidence.loc[
        evidence["account_id"].eq(account_id)
        & evidence["evaluation_status"].eq("triggered")
    ]
    return [str(value) for value in rows["human_explanation"].dropna().tolist()]


def _build_explanation(row: pd.Series, evidence: pd.DataFrame) -> str:
    triggered_rules = _as_list(row.get("triggered_rule_ids"))
    evidence_text = " ".join(_triggered_explanations(evidence, str(row["account_id"])))
    rule_text = ", ".join(triggered_rules) if triggered_rules else "no mandatory rule"
    base = (
        f"Suspicious indicator for account {row['account_id']} requires human review. "
        f"Risk score {int(row['risk_score'])} ({row['risk_level']}) met alert criteria. "
        f"Triggered rules: {rule_text}."
    )
    if evidence_text:
        return (
            f"{base} Evidence: {evidence_text} "
            "This output is an investigative aid and does not make an account decision."
        )
    return f"{base} This output is an investigative aid and does not make an account decision."


def _mandatory_rule_ids(rules_path: Path | str) -> set[str]:
    config = load_rules_config(rules_path)
    return {
        rule_id
        for rule_id, rule in config.rules.items()
        if rule.enabled and rule.mandatory
    }


def _should_alert(row: pd.Series, alert_min_score: int, mandatory_rules: set[str]) -> bool:
    if int(row["risk_score"]) >= alert_min_score:
        return True
    triggered = set(_as_list(row.get("triggered_rule_ids")))
    return bool(triggered & mandatory_rules)


def _alert_record(row: pd.Series, evidence: pd.DataFrame) -> dict[str, object]:
    alert_id = f"ALERT_{row['run_id']}_{row['account_id']}"
    return {
        "alert_id": alert_id,
        "run_id": row["run_id"],
        "account_id": row["account_id"],
        "risk_score": int(row["risk_score"]),
        "risk_level": row["risk_level"],
        "alert_status": "new",
        "triggered_rule_ids": _as_list(row.get("triggered_rule_ids")),
        "triggered_rule_count": int(row.get("triggered_rule_count", 0)),
        "explanation": _build_explanation(row, evidence),
        "first_activity_at": row.get("first_activity_at"),
        "last_activity_at": row.get("last_activity_at"),
        "incoming_amount_7d": row.get("incoming_amount_7d"),
        "outgoing_amount_7d": row.get("outgoing_amount_7d"),
        "unique_senders_7d": row.get("unique_senders_7d"),
        "unique_receivers_7d": row.get("unique_receivers_7d"),
        "hold_time_proxy_minutes": row.get("hold_time_proxy_minutes"),
        "cluster_id": None,
        "source_data_fingerprint": row.get("source_data_fingerprint"),
        "rules_config_hash": row.get("rules_config_hash"),
        "created_at": row.get("created_at"),
        "okf_concept_id": f"alerts/{alert_id}",
    }


def _write_alerts(run_path: Path, alerts: pd.DataFrame) -> Path:
    alerts_path = run_path / "alerts.parquet"
    alerts.to_parquet(alerts_path, index=False)
    duckdb_path = run_path / "transactions.duckdb"
    with duckdb.connect(str(duckdb_path)) as connection:
        connection.register("alerts_df", alerts)
        connection.execute("create or replace table alerts as select * from alerts_df")
        connection.unregister("alerts_df")
    return alerts_path


def generate_alerts(
    run_dir: Path | str,
    *,
    rules_path: Path | str = "config/rules.yaml",
) -> AlertGenerationResult:
    """Generate analyst-review alerts from account risk and rule evidence artifacts."""

    run_path = Path(run_dir)
    risk = pd.read_parquet(run_path / "account_risk.parquet")
    evidence = pd.read_parquet(run_path / "rule_evidence.parquet")
    config = load_rules_config(rules_path)
    mandatory_rules = _mandatory_rule_ids(rules_path)

    records = [
        _alert_record(row, evidence)
        for _, row in risk.iterrows()
        if _should_alert(row, config.alert_min_score, mandatory_rules)
    ]
    alerts = pd.DataFrame(records, columns=ALERT_COLUMNS)
    alerts_path = _write_alerts(run_path, alerts)
    return AlertGenerationResult(
        run_id=run_path.name,
        run_dir=run_path,
        alerts_path=alerts_path,
        alert_count=int(len(alerts)),
    )
