from pathlib import Path

import pandas as pd

from fraud_demo.scoring import risk_level_for_score, score_accounts


def _feature_row(account_id: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "run_id": "RUN_SCORING",
        "account_id": account_id,
        "snapshot_timestamp": "2026-01-08T12:00:00+00:00",
        "first_activity_at": "2026-01-08T08:00:00+00:00",
        "last_activity_at": "2026-01-08T12:00:00+00:00",
        "incoming_count_24h": 0,
        "outgoing_count_24h": 0,
        "incoming_amount_24h": 0.0,
        "outgoing_amount_24h": 0.0,
        "unique_senders_7d": 0,
        "unique_receivers_7d": 0,
        "incoming_amount_7d": 0.0,
        "outgoing_amount_7d": 0.0,
        "pass_through_ratio_7d": 0.0,
        "hold_time_proxy_minutes": 999.0,
        "cross_border_out_ratio_7d": 0.0,
        "night_activity_ratio_7d": 0.0,
        "round_amount_ratio_7d": 0.0,
        "shared_device_account_count_30d": 1,
        "shared_ip_account_count_30d": 1,
        "account_age_days": 365,
        "active_days_30d": 1,
        "counterparty_concentration_7d": 0.0,
        "reciprocal_transfer_ratio_7d": 0.0,
        "short_cycle_flag": False,
    }
    row.update(overrides)
    return row


def _write_features(run_dir: Path, rows: list[dict[str, object]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(run_dir / "account_features.parquet", index=False)
    (run_dir / "run_manifest.json").write_text(
        '{"source_data_fingerprint":"source-sha","artifact_paths":{}}\n',
        encoding="utf-8",
    )


def test_risk_level_for_score_uses_configured_boundaries():
    bands = {
        "low": (0, 24),
        "medium": (25, 49),
        "high": (50, 74),
        "critical": (75, 100),
    }

    assert risk_level_for_score(24, bands) == "Low"
    assert risk_level_for_score(25, bands) == "Medium"
    assert risk_level_for_score(50, bands) == "High"
    assert risk_level_for_score(75, bands) == "Critical"


def test_score_accounts_evaluates_each_baseline_rule_at_threshold(tmp_path: Path):
    run_dir = tmp_path / "artifacts" / "runs" / "RUN_SCORING"
    _write_features(
        run_dir,
        [
            _feature_row("ACC_BELOW", unique_senders_7d=9),
            _feature_row("ACC_HIGH_FAN_IN", unique_senders_7d=10),
            _feature_row(
                "ACC_RAPID",
                incoming_amount_7d=1_000,
                outgoing_amount_7d=800,
                pass_through_ratio_7d=0.8,
                hold_time_proxy_minutes=120,
            ),
            _feature_row("ACC_HIGH_VELOCITY", incoming_count_24h=15, outgoing_count_24h=15),
            _feature_row("ACC_HIGH_FAN_OUT", unique_receivers_7d=10),
            _feature_row("ACC_SHARED", shared_device_account_count_30d=4),
            _feature_row(
                "ACC_CROSS_BORDER",
                incoming_amount_7d=10_000,
                cross_border_out_ratio_7d=0.5,
            ),
            _feature_row(
                "ACC_NEW_BURST",
                account_age_days=30,
                incoming_count_24h=10,
                outgoing_count_24h=10,
            ),
            _feature_row("ACC_SHORT_CYCLE", short_cycle_flag=True),
            _feature_row(
                "ACC_HIGH",
                unique_senders_7d=10,
                incoming_count_24h=20,
                outgoing_count_24h=10,
                incoming_amount_7d=1_000,
                outgoing_amount_7d=800,
                pass_through_ratio_7d=0.8,
                hold_time_proxy_minutes=120,
            ),
            _feature_row(
                "ACC_CAPPED",
                unique_senders_7d=20,
                unique_receivers_7d=20,
                incoming_count_24h=30,
                outgoing_count_24h=30,
                incoming_amount_7d=20_000,
                outgoing_amount_7d=20_000,
                pass_through_ratio_7d=1.0,
                hold_time_proxy_minutes=30,
                cross_border_out_ratio_7d=0.9,
                shared_device_account_count_30d=6,
                shared_ip_account_count_30d=6,
                account_age_days=5,
                short_cycle_flag=True,
            ),
            _feature_row(
                "ACC_UNAVAILABLE",
                hold_time_proxy_minutes=pd.NA,
                cross_border_out_ratio_7d=pd.NA,
                shared_device_account_count_30d=pd.NA,
                shared_ip_account_count_30d=pd.NA,
                account_age_days=pd.NA,
                short_cycle_flag=pd.NA,
            ),
        ],
    )

    result = score_accounts(run_dir)

    risk = pd.read_parquet(result.account_risk_path).set_index("account_id")
    evidence = pd.read_parquet(result.rule_evidence_path)
    assert risk.loc["ACC_BELOW", "risk_score"] == 0
    assert risk.loc["ACC_HIGH", "risk_score"] == 60
    assert risk.loc["ACC_HIGH", "risk_level"] == "High"
    assert risk.loc["ACC_CAPPED", "risk_score"] == 100
    assert risk.loc["ACC_CAPPED", "risk_level"] == "Critical"
    assert "rapid_pass_through" in risk.loc["ACC_HIGH", "triggered_rule_ids"]
    assert risk.loc["ACC_HIGH", "source_data_fingerprint"] == "source-sha"
    assert len(result.rules_config_hash) == 64
    assert result.evidence_count == len(evidence)

    expected = {
        "ACC_HIGH_FAN_IN": "high_fan_in",
        "ACC_RAPID": "rapid_pass_through",
        "ACC_HIGH_VELOCITY": "high_velocity",
        "ACC_HIGH_FAN_OUT": "high_fan_out",
        "ACC_SHARED": "shared_access_point",
        "ACC_CROSS_BORDER": "cross_border_funnel",
        "ACC_NEW_BURST": "new_account_burst",
        "ACC_SHORT_CYCLE": "short_cycle",
    }
    for account_id, rule_id in expected.items():
        account_evidence = evidence.loc[
            evidence["account_id"].eq(account_id) & evidence["rule_id"].eq(rule_id)
        ].iloc[0]
        assert account_evidence["evaluation_status"] == "triggered"
        assert bool(account_evidence["triggered"]) is True
        assert rule_id in account_evidence["human_explanation"]

    unavailable = evidence.loc[evidence["account_id"].eq("ACC_UNAVAILABLE")]
    assert set(unavailable["evaluation_status"]) >= {"not_triggered", "not_evaluated"}
    assert (
        unavailable.loc[
            unavailable["rule_id"].eq("rapid_pass_through"),
            "evaluation_status",
        ].iloc[0]
        == "not_evaluated"
    )
    assert evidence.loc[
        evidence["rule_id"].eq("rapid_pass_through"),
        "thresholds_json",
    ].str.contains("0.8").any()
