import json

from fraud_demo.okf_validator import validate_okf_bundle


def _write_valid_bundle(tmp_path):
    bundle = tmp_path / "okf_bundle"
    (bundle / "accounts").mkdir(parents=True)
    (bundle / "index.md").write_text('---\nokf_version: "0.1"\n---\n\n# Bundle\n', encoding="utf-8")
    (bundle / "log.md").write_text("# Log\n\n## 2026-06-22\n\n- Created.\n", encoding="utf-8")
    (bundle / "accounts" / "index.md").write_text("# Accounts\n", encoding="utf-8")
    (bundle / "accounts" / "ACC001.md").write_text(
        """---
type: Fraud Account
title: Account ACC001
description: Suspicious indicator requiring human review.
timestamp: 2026-06-22T00:00:00+00:00
---

# Account ACC001
""",
        encoding="utf-8",
    )
    return bundle


def _codes(items):
    return {item["code"] for item in items}


def test_validate_okf_bundle_accepts_valid_bundle_and_writes_report(tmp_path):
    bundle = _write_valid_bundle(tmp_path)
    report_path = tmp_path / "report.json"

    result = validate_okf_bundle(bundle, report_path=report_path)

    assert result.valid is True
    assert result.concept_count == 1
    assert result.link_count == 0
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["okf_version"] == "0.1"
    assert report["valid"] is True
    assert report["hard_errors"] == []
    assert report["concept_count"] == 1


def test_validate_okf_bundle_reports_hard_frontmatter_errors(tmp_path):
    bundle = _write_valid_bundle(tmp_path)
    (bundle / "accounts" / "NO_FRONTMATTER.md").write_text("# Missing\n", encoding="utf-8")
    (bundle / "accounts" / "BAD_YAML.md").write_text(
        "---\ntitle: [unterminated\n---\n# Bad\n",
        encoding="utf-8",
    )
    (bundle / "accounts" / "EMPTY_TYPE.md").write_text(
        '---\ntype: ""\n---\n# Empty\n',
        encoding="utf-8",
    )
    (bundle / "alerts").mkdir()
    (bundle / "alerts" / "index.md").write_text(
        "---\ntype: Fraud Alert\n---\n# Reserved\n",
        encoding="utf-8",
    )

    result = validate_okf_bundle(bundle)

    assert result.valid is False
    assert {
        "missing_frontmatter",
        "invalid_frontmatter",
        "missing_type",
        "reserved_frontmatter",
    }.issubset(_codes(result.hard_errors))


def test_validate_okf_bundle_warns_for_broken_links_relations_and_indexes(tmp_path):
    bundle = _write_valid_bundle(tmp_path)
    (bundle / "signals").mkdir()
    (bundle / "signals" / "rapid_pass_through.md").write_text(
        """---
type: Fraud Signal
title: Rapid pass-through
description: Signal.
timestamp: 2026-06-22T00:00:00+00:00
relations:
  - predicate: triggered_by
    target_concept_id: accounts/MISSING_RELATION
---

# Signal

[Missing account](../accounts/MISSING_LINK.md)
""",
        encoding="utf-8",
    )

    result = validate_okf_bundle(bundle)

    assert result.valid is True
    assert {
        "broken_link",
        "broken_relation",
        "missing_directory_index",
    }.issubset(_codes(result.warnings))
