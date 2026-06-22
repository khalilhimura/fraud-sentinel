from pathlib import Path

import pandas as pd

from fraud_demo.alerts import generate_alerts


def test_generate_alerts_writes_only_review_threshold_alerts(tmp_path: Path):
    run_dir = tmp_path / "artifacts" / "runs" / "RUN_ALERTS"
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "run_id": "RUN_ALERTS",
                "account_id": "ACC_HIGH",
                "risk_score": 60,
                "risk_level": "High",
                "alert_status": "new",
                "triggered_rule_ids": ["high_fan_in", "rapid_pass_through"],
                "triggered_rule_count": 2,
                "first_activity_at": "2026-01-08T08:00:00+00:00",
                "last_activity_at": "2026-01-08T12:00:00+00:00",
                "incoming_amount_7d": 10_000.0,
                "outgoing_amount_7d": 8_500.0,
                "unique_senders_7d": 10,
                "unique_receivers_7d": 1,
                "hold_time_proxy_minutes": 60.0,
                "source_data_fingerprint": "source-sha",
                "rules_config_hash": "a" * 64,
                "created_at": "2026-01-08T12:00:00+00:00",
            },
            {
                "run_id": "RUN_ALERTS",
                "account_id": "ACC_MEDIUM",
                "risk_score": 49,
                "risk_level": "Medium",
                "alert_status": "new",
                "triggered_rule_ids": ["rapid_pass_through"],
                "triggered_rule_count": 1,
                "first_activity_at": "2026-01-08T08:00:00+00:00",
                "last_activity_at": "2026-01-08T12:00:00+00:00",
                "incoming_amount_7d": 1_000.0,
                "outgoing_amount_7d": 800.0,
                "unique_senders_7d": 1,
                "unique_receivers_7d": 1,
                "hold_time_proxy_minutes": 60.0,
                "source_data_fingerprint": "source-sha",
                "rules_config_hash": "a" * 64,
                "created_at": "2026-01-08T12:00:00+00:00",
            },
        ]
    ).to_parquet(run_dir / "account_risk.parquet", index=False)
    pd.DataFrame(
        [
            {
                "run_id": "RUN_ALERTS",
                "account_id": "ACC_HIGH",
                "rule_id": "high_fan_in",
                "evaluation_status": "triggered",
                "triggered": True,
                "human_explanation": "high_fan_in triggered because unique_senders_7d=10.",
            },
            {
                "run_id": "RUN_ALERTS",
                "account_id": "ACC_HIGH",
                "rule_id": "rapid_pass_through",
                "evaluation_status": "triggered",
                "triggered": True,
                "human_explanation": (
                    "rapid_pass_through triggered because pass-through evidence matched."
                ),
            },
        ]
    ).to_parquet(run_dir / "rule_evidence.parquet", index=False)
    (run_dir / "run_manifest.json").write_text(
        '{"source_data_fingerprint":"source-sha"}\n',
        encoding="utf-8",
    )

    result = generate_alerts(run_dir)

    alerts = pd.read_parquet(result.alerts_path)
    assert result.alert_count == 1
    assert alerts.loc[0, "alert_id"] == "ALERT_RUN_ALERTS_ACC_HIGH"
    assert alerts.loc[0, "alert_status"] == "new"
    assert alerts.loc[0, "okf_concept_id"] == "alerts/ALERT_RUN_ALERTS_ACC_HIGH"
    assert "requires human review" in alerts.loc[0, "explanation"]
    assert "confirmed fraud" not in alerts.loc[0, "explanation"].lower()
    assert alerts.loc[0, "rules_config_hash"] == "a" * 64
