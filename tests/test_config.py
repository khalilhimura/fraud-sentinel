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
