"""OKF v0.1 bundle export for Phase 5."""

from __future__ import annotations

import html
import json
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import yaml
from jinja2 import Environment, PackageLoader, select_autoescape

from fraud_demo import __version__
from fraud_demo.config import load_rules_config

RESERVED_FILENAMES = {"index", "log"}
OPTIONAL_INDEX_DIRS = [
    "accounts",
    "alerts",
    "clusters",
    "signals",
    "devices",
    "ips",
    "metrics",
    "runs",
    "datasets",
    "runbooks",
    "references",
]
SUSPICIOUS_LEVELS = {"high", "critical"}


@dataclass(frozen=True)
class OkfExportResult:
    """Artifacts and counts from OKF bundle export."""

    run_id: str
    run_dir: Path
    bundle_path: Path
    okf_manifest_path: Path
    concept_count: int
    account_count: int
    alert_count: int
    cluster_count: int


def _read_yaml(path: Path | str) -> dict[str, Any]:
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{config_path} must contain a YAML mapping")
    return data


def _json_loads(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    if not isinstance(value, str):
        return default
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _as_list(value: Any) -> list[str]:
    loaded = _json_loads(value, None)
    if isinstance(loaded, list):
        return [str(item) for item in loaded]
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if hasattr(value, "tolist"):
        return [str(item) for item in value.tolist()]
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass
    if value is None or value == "":
        return []
    return [str(value)]


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _safe_text(value: Any) -> str:
    if _is_missing(value):
        return ""
    text = str(value).replace("\n", " ").replace("\r", " ")
    return html.escape(text, quote=False).replace("|", "\\|")


def _safe_number(value: Any, default: float = 0.0) -> float:
    if _is_missing(value):
        return default
    return float(pd.to_numeric(value, errors="coerce") or default)


def _safe_int(value: Any, default: int = 0) -> int:
    return int(_safe_number(value, float(default)))


def _title_from_id(identifier: str) -> str:
    text = identifier.replace("_", " ").replace("-", " ").lower()
    text = text.replace("pass through", "pass-through")
    text = text.replace("fan in", "fan-in")
    text = text.replace("fan out", "fan-out")
    return text[:1].upper() + text[1:]


def _slug(value: Any) -> str:
    text = str(value).strip().replace("/", "_").replace("\\", "_")
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    text = text.strip("._")
    if not text:
        text = "concept"
    if text.lower() in RESERVED_FILENAMES:
        text = f"{text}_"
    return text


def _concept_id(directory: str, identifier: Any) -> str:
    return f"{directory}/{_slug(identifier)}"


def _relative_link(from_concept_id: str, to_concept_id: str, label: str) -> str:
    source_parent = Path(from_concept_id).parent
    target_path = Path(f"{to_concept_id}.md")
    if str(source_parent) == ".":
        destination = target_path.as_posix()
    else:
        destination = Path(
            *(
                [".."] * len(source_parent.parts)
            ),
            target_path,
        ).as_posix()
    if from_concept_id.split("/", 1)[0] == to_concept_id.split("/", 1)[0]:
        destination = Path(to_concept_id.split("/", 1)[1] + ".md").as_posix()
    return f"[{_safe_text(label)}]({destination})"


def _frontmatter(data: dict[str, Any]) -> str:
    clean = {key: value for key, value in data.items() if value is not None}
    return yaml.safe_dump(clean, sort_keys=False, allow_unicode=False).strip()


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _template_env() -> Environment:
    env = Environment(
        loader=PackageLoader("fraud_demo", "templates"),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["safe_text"] = _safe_text
    return env


def _required_artifacts(run_path: Path) -> dict[str, pd.DataFrame]:
    return {
        "account_risk": pd.read_parquet(run_path / "account_risk.parquet"),
        "alerts": pd.read_parquet(run_path / "alerts.parquet"),
        "rule_evidence": pd.read_parquet(run_path / "rule_evidence.parquet"),
        "graph_nodes": pd.read_parquet(run_path / "graph_nodes.parquet"),
        "graph_edges": pd.read_parquet(run_path / "graph_edges.parquet"),
        "clusters": pd.read_parquet(run_path / "clusters.parquet"),
    }


def _sort_by_columns(
    frame: pd.DataFrame,
    columns: list[str],
    ascending: list[bool],
) -> pd.DataFrame:
    existing = [column for column in columns if column in frame.columns]
    if not existing:
        return frame.copy()
    return frame.copy().sort_values(
        existing,
        ascending=ascending[: len(existing)],
        kind="mergesort",
    )


def _select_alerts(alerts: pd.DataFrame, limit: int) -> pd.DataFrame:
    if alerts.empty or limit <= 0:
        return alerts.head(0).copy()
    frame = alerts.copy()
    frame["risk_score"] = pd.to_numeric(frame.get("risk_score"), errors="coerce").fillna(0)
    return _sort_by_columns(frame, ["risk_score", "alert_id"], [False, True]).head(limit)


def _select_clusters(clusters: pd.DataFrame, limit: int) -> pd.DataFrame:
    if clusters.empty or limit <= 0:
        return clusters.head(0).copy()
    frame = clusters.copy()
    for column in ["max_risk_score", "suspicious_account_count", "total_transfer_amount"]:
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce").fillna(0)
    return _sort_by_columns(
        frame,
        ["max_risk_score", "suspicious_account_count", "total_transfer_amount", "cluster_id"],
        [False, False, False, True],
    ).head(limit)


def _select_accounts(
    risk: pd.DataFrame,
    alerts: pd.DataFrame,
    graph_nodes: pd.DataFrame,
    limit: int,
) -> pd.DataFrame:
    if risk.empty or limit <= 0:
        return risk.head(0).copy()
    risk_frame = risk.copy()
    risk_frame["risk_score"] = pd.to_numeric(
        risk_frame.get("risk_score"),
        errors="coerce",
    ).fillna(0)
    risk_by_account = {str(row["account_id"]): row for _, row in risk_frame.iterrows()}
    ordered_ids: list[str] = []

    def add(account_id: Any) -> None:
        text = str(account_id)
        if text in risk_by_account and text not in ordered_ids:
            ordered_ids.append(text)

    for account_id in alerts.get("account_id", pd.Series(dtype=str)).tolist():
        add(account_id)

    suspicious = risk_frame.loc[
        risk_frame["risk_level"].astype(str).str.lower().isin(SUSPICIOUS_LEVELS)
    ]
    suspicious = _sort_by_columns(suspicious, ["risk_score", "account_id"], [False, True])
    for account_id in suspicious.get("account_id", pd.Series(dtype=str)).tolist():
        add(account_id)

    account_nodes = graph_nodes.loc[graph_nodes.get("node_type", "").eq("Account")].copy()
    if not account_nodes.empty:
        account_nodes["risk_score"] = pd.to_numeric(
            account_nodes.get("risk_score"),
            errors="coerce",
        ).fillna(0)
        account_nodes["is_suspicious_sort"] = account_nodes.get(
            "is_suspicious",
            False,
        ).fillna(False).astype(bool)
        account_nodes["is_context_sort"] = account_nodes.get("is_context", False).fillna(
            False
        ).astype(bool)
        account_nodes = account_nodes.sort_values(
            ["is_suspicious_sort", "risk_score", "is_context_sort", "account_id"],
            ascending=[False, False, True, True],
            kind="mergesort",
        )
        for account_id in account_nodes["account_id"].tolist():
            add(account_id)

    selected = [risk_by_account[account_id] for account_id in ordered_ids[:limit]]
    return pd.DataFrame(selected)


def _concept_maps(
    accounts: pd.DataFrame,
    alerts: pd.DataFrame,
    clusters: pd.DataFrame,
    rule_ids: list[str],
    run_id: str,
) -> dict[str, dict[str, str]]:
    return {
        "accounts": {
            str(row["account_id"]): _concept_id("accounts", row["account_id"])
            for _, row in accounts.iterrows()
        },
        "alerts": {
            str(row["alert_id"]): _concept_id("alerts", row["alert_id"])
            for _, row in alerts.iterrows()
        },
        "clusters": {
            str(row["cluster_id"]): _concept_id("clusters", row["cluster_id"])
            for _, row in clusters.iterrows()
        },
        "signals": {rule_id: _concept_id("signals", rule_id) for rule_id in rule_ids},
        "runs": {run_id: _concept_id("runs", run_id)},
        "datasets": {"transactions": "datasets/transactions"},
        "runbooks": {"mule_account_investigation": "runbooks/mule_account_investigation"},
    }


def _evidence_for_account(evidence: pd.DataFrame, account_id: str) -> list[dict[str, str]]:
    if evidence.empty:
        return []
    rows = evidence.loc[
        evidence["account_id"].astype(str).eq(account_id)
        & evidence["evaluation_status"].astype(str).eq("triggered")
    ]
    records: list[dict[str, str]] = []
    for _, row in rows.iterrows():
        values = _json_loads(row.get("feature_values_json"), {})
        thresholds = _json_loads(row.get("thresholds_json"), {})
        records.append(
            {
                "rule_id": str(row.get("rule_id")),
                "rule_label": _title_from_id(str(row.get("rule_id"))),
                "feature_values": ", ".join(
                    f"{_safe_text(key)}={_safe_text(value)}" for key, value in values.items()
                ),
                "thresholds": ", ".join(
                    f"{_safe_text(key)}={_safe_text(value)}" for key, value in thresholds.items()
                ),
                "explanation": _safe_text(row.get("human_explanation")),
            }
        )
    return records


def _account_links(
    account_id: str,
    concept_id: str,
    row: pd.Series,
    maps: dict[str, dict[str, str]],
    graph_edges: pd.DataFrame,
) -> dict[str, list[str]]:
    signal_links = []
    for rule_id in _as_list(row.get("triggered_rule_ids")):
        target = maps["signals"].get(rule_id)
        if target:
            signal_links.append(_relative_link(concept_id, target, _title_from_id(rule_id)))

    alert_links = []
    for alert_id, alert_concept in maps["alerts"].items():
        if alert_id.endswith(f"_{account_id}"):
            alert_links.append(_relative_link(concept_id, alert_concept, f"Alert {alert_id}"))

    cluster_links = []
    cluster_id = row.get("cluster_id")
    if not _is_missing(cluster_id) and str(cluster_id) in maps["clusters"]:
        cluster_links.append(
            _relative_link(concept_id, maps["clusters"][str(cluster_id)], f"Cluster {cluster_id}")
        )

    connected_links = []
    transfers = graph_edges.loc[
        graph_edges.get("edge_type", "").eq("TRANSFERRED_TO")
        & (
            graph_edges.get("source_node_id", "").astype(str).eq(account_id)
            | graph_edges.get("target_node_id", "").astype(str).eq(account_id)
        )
    ]
    seen: set[str] = set()
    for edge in transfers.itertuples(index=False):
        other = (
            str(edge.target_node_id)
            if str(edge.source_node_id) == account_id
            else str(edge.source_node_id)
        )
        target = maps["accounts"].get(other)
        if target and other not in seen:
            connected_links.append(_relative_link(concept_id, target, f"Account {other}"))
            seen.add(other)

    return {
        "signals": signal_links,
        "alerts": alert_links,
        "clusters": cluster_links,
        "connected_accounts": connected_links,
    }


def _relations_enabled(config: dict[str, Any]) -> bool:
    return bool(config.get("include_typed_relations_extension", False))


def _base_frontmatter(
    concept_type: str,
    title: str,
    description: str,
    run_id: str,
    resource: str,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": concept_type,
        "title": title,
        "description": description,
        "tags": ["fraud", "human-review"],
        "timestamp": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "producer": "fraud-agentic-demo",
        "producer_version": __version__,
        "source_data_fingerprint": manifest.get("source_data_fingerprint"),
        "rules_config_hash": manifest.get("rules_config_hash"),
        "code_commit": manifest.get("code_commit"),
        "resource": resource,
    }


def _render_account(
    env: Environment,
    bundle: Path,
    row: pd.Series,
    *,
    run_id: str,
    concept_id: str,
    concept_type: str,
    manifest: dict[str, Any],
    maps: dict[str, dict[str, str]],
    evidence: pd.DataFrame,
    graph_edges: pd.DataFrame,
    include_relations: bool,
) -> None:
    account_id = str(row["account_id"])
    description = (
        f"{row.get('risk_level', 'Unknown')}-risk suspicious account indicator "
        "requiring human review."
    )
    links = _account_links(account_id, concept_id, row, maps, graph_edges)
    frontmatter = _base_frontmatter(
        concept_type,
        f"Account {account_id}",
        description,
        run_id,
        f"fraud-demo://account/{account_id}",
        manifest,
    )
    frontmatter.update(
        {
            "account_id": account_id,
            "risk_score": _safe_int(row.get("risk_score")),
            "risk_level": str(row.get("risk_level")),
        }
    )
    relations = []
    for rule_id in _as_list(row.get("triggered_rule_ids")):
        if rule_id in maps["signals"]:
            relations.append(
                {"predicate": "triggered_signal", "target_concept_id": maps["signals"][rule_id]}
            )
    cluster_id = row.get("cluster_id")
    if not _is_missing(cluster_id) and str(cluster_id) in maps["clusters"]:
        relations.append(
            {
                "predicate": "member_of_cluster",
                "target_concept_id": maps["clusters"][str(cluster_id)],
            }
        )
    if include_relations and relations:
        frontmatter["relations"] = relations

    context = {
        "frontmatter": _frontmatter(frontmatter),
        "account_id": account_id,
        "risk_score": _safe_int(row.get("risk_score")),
        "risk_level": _safe_text(row.get("risk_level")),
        "links": links,
        "evidence": _evidence_for_account(evidence, account_id),
        "runbook_link": _relative_link(
            concept_id,
            maps["runbooks"]["mule_account_investigation"],
            "Mule-account investigation runbook",
        ),
    }
    _write_markdown(bundle / f"{concept_id}.md", env.get_template("account.md.j2").render(context))


def _render_alert(
    env: Environment,
    bundle: Path,
    row: pd.Series,
    *,
    run_id: str,
    concept_id: str,
    concept_type: str,
    manifest: dict[str, Any],
    maps: dict[str, dict[str, str]],
    evidence: pd.DataFrame,
    include_relations: bool,
) -> None:
    alert_id = str(row["alert_id"])
    account_id = str(row["account_id"])
    frontmatter = _base_frontmatter(
        concept_type,
        f"Alert {alert_id}",
        "Explainable suspicious account alert requiring human review.",
        run_id,
        f"fraud-demo://alert/{alert_id}",
        manifest,
    )
    frontmatter.update(
        {
            "alert_id": alert_id,
            "account_id": account_id,
            "risk_score": _safe_int(row.get("risk_score")),
            "risk_level": str(row.get("risk_level")),
        }
    )
    relations = []
    if account_id in maps["accounts"]:
        relations.append(
            {
                "predicate": "has_account",
                "target_concept_id": maps["accounts"][account_id],
            }
        )
    for rule_id in _as_list(row.get("triggered_rule_ids")):
        if rule_id in maps["signals"]:
            relations.append(
                {"predicate": "triggered_signal", "target_concept_id": maps["signals"][rule_id]}
            )
    cluster_id = row.get("cluster_id")
    if not _is_missing(cluster_id) and str(cluster_id) in maps["clusters"]:
        relations.append(
            {
                "predicate": "member_of_cluster",
                "target_concept_id": maps["clusters"][str(cluster_id)],
            }
        )
    if include_relations and relations:
        frontmatter["relations"] = relations
    context = {
        "frontmatter": _frontmatter(frontmatter),
        "alert_id": alert_id,
        "account_link": _relative_link(
            concept_id,
            maps["accounts"].get(account_id, f"accounts/{_slug(account_id)}"),
            f"Account {account_id}",
        ),
        "cluster_link": (
            _relative_link(concept_id, maps["clusters"][str(cluster_id)], f"Cluster {cluster_id}")
            if not _is_missing(cluster_id) and str(cluster_id) in maps["clusters"]
            else None
        ),
        "risk_score": _safe_int(row.get("risk_score")),
        "risk_level": _safe_text(row.get("risk_level")),
        "signal_links": [
            _relative_link(concept_id, maps["signals"][rule_id], _title_from_id(rule_id))
            for rule_id in _as_list(row.get("triggered_rule_ids"))
            if rule_id in maps["signals"]
        ],
        "evidence": _evidence_for_account(evidence, account_id),
        "run_link": _relative_link(concept_id, maps["runs"][run_id], f"Run {run_id}"),
        "runbook_link": _relative_link(
            concept_id,
            maps["runbooks"]["mule_account_investigation"],
            "Mule-account investigation runbook",
        ),
    }
    _write_markdown(bundle / f"{concept_id}.md", env.get_template("alert.md.j2").render(context))


def _render_cluster(
    env: Environment,
    bundle: Path,
    row: pd.Series,
    *,
    run_id: str,
    concept_id: str,
    concept_type: str,
    manifest: dict[str, Any],
    maps: dict[str, dict[str, str]],
    alerts: pd.DataFrame,
    include_relations: bool,
) -> None:
    cluster_id = str(row["cluster_id"])
    member_ids = [
        item
        for item in _as_list(row.get("member_account_ids_json"))
        if item in maps["accounts"]
    ]
    alert_ids = [
        str(alert["alert_id"])
        for _, alert in alerts.iterrows()
        if str(alert.get("cluster_id")) == cluster_id
        and str(alert.get("alert_id")) in maps["alerts"]
    ]
    frontmatter = _base_frontmatter(
        concept_type,
        f"Cluster {cluster_id}",
        "Suspicious connected account cluster requiring human review.",
        run_id,
        f"fraud-demo://cluster/{cluster_id}",
        manifest,
    )
    frontmatter.update(
        {
            "cluster_id": cluster_id,
            "max_risk_score": _safe_int(row.get("max_risk_score")),
            "account_count": _safe_int(row.get("account_count")),
        }
    )
    relations = [
        {"predicate": "has_member", "target_concept_id": maps["accounts"][account_id]}
        for account_id in member_ids
    ]
    if include_relations and relations:
        frontmatter["relations"] = relations
    context = {
        "frontmatter": _frontmatter(frontmatter),
        "cluster_id": cluster_id,
        "account_count": _safe_int(row.get("account_count")),
        "suspicious_account_count": _safe_int(row.get("suspicious_account_count")),
        "total_transfer_amount": _safe_number(row.get("total_transfer_amount")),
        "max_risk_score": _safe_int(row.get("max_risk_score")),
        "member_links": [
            _relative_link(concept_id, maps["accounts"][account_id], f"Account {account_id}")
            for account_id in member_ids
        ],
        "alert_links": [
            _relative_link(concept_id, maps["alerts"][alert_id], f"Alert {alert_id}")
            for alert_id in alert_ids
        ],
        "short_cycle_detected": bool(row.get("short_cycle_detected")),
    }
    _write_markdown(bundle / f"{concept_id}.md", env.get_template("cluster.md.j2").render(context))


def _render_signal(
    env: Environment,
    bundle: Path,
    rule_id: str,
    rule: Any,
    *,
    run_id: str,
    concept_id: str,
    concept_type: str,
    manifest: dict[str, Any],
    maps: dict[str, dict[str, str]],
    include_relations: bool,
) -> None:
    frontmatter = _base_frontmatter(
        concept_type,
        _title_from_id(rule_id),
        str(rule.description),
        run_id,
        f"fraud-demo://signal/{rule_id}",
        manifest,
    )
    frontmatter.update({"rule_id": rule_id, "rule_weight": int(rule.weight)})
    if include_relations:
        frontmatter["relations"] = [
            {"predicate": "generated_in_run", "target_concept_id": maps["runs"][run_id]}
        ]
    context = {
        "frontmatter": _frontmatter(frontmatter),
        "rule_id": rule_id,
        "title": _title_from_id(rule_id),
        "description": _safe_text(rule.description),
        "weight": int(rule.weight),
        "required_features": [_safe_text(value) for value in rule.required_features],
        "thresholds": {str(key): _safe_text(value) for key, value in rule.thresholds.items()},
        "run_link": _relative_link(concept_id, maps["runs"][run_id], f"Run {run_id}"),
    }
    _write_markdown(bundle / f"{concept_id}.md", env.get_template("signal.md.j2").render(context))


def _render_run_dataset_runbook(
    env: Environment,
    bundle: Path,
    *,
    run_id: str,
    config: dict[str, Any],
    manifest: dict[str, Any],
    maps: dict[str, dict[str, str]],
    concept_types: dict[str, str],
) -> int:
    run_concept = maps["runs"][run_id]
    dataset_concept = maps["datasets"]["transactions"]
    runbook_concept = maps["runbooks"]["mule_account_investigation"]
    run_frontmatter = _base_frontmatter(
        concept_types["run"],
        f"Run {run_id}",
        "Pipeline run provenance for the fraud demo.",
        run_id,
        f"fraud-demo://run/{run_id}",
        manifest,
    )
    run_frontmatter["relations"] = [
        {"predicate": "derived_from_dataset", "target_concept_id": dataset_concept}
    ] if _relations_enabled(config) else None
    _write_markdown(
        bundle / f"{run_concept}.md",
        env.get_template("run.md.j2").render(
            {
                "frontmatter": _frontmatter(run_frontmatter),
                "run_id": run_id,
                "status": _safe_text(manifest.get("status")),
                "source_data_fingerprint": _safe_text(manifest.get("source_data_fingerprint")),
                "rules_config_hash": _safe_text(manifest.get("rules_config_hash")),
                "dataset_link": _relative_link(
                    run_concept,
                    dataset_concept,
                    "Transactions dataset",
                ),
            }
        ),
    )

    dataset_frontmatter = _base_frontmatter(
        concept_types["dataset"],
        "Transactions Dataset",
        "Dataset-level summary for the processed transaction input.",
        run_id,
        "fraud-demo://dataset/transactions",
        manifest,
    )
    dataset_frontmatter["relations"] = [
        {"predicate": "generated_in_run", "target_concept_id": run_concept}
    ] if _relations_enabled(config) else None
    _write_markdown(
        bundle / f"{dataset_concept}.md",
        env.get_template("run.md.j2").render(
            {
                "frontmatter": _frontmatter(dataset_frontmatter),
                "run_id": "Transactions dataset",
                "status": "Processed aggregate dataset only",
                "source_data_fingerprint": _safe_text(manifest.get("source_data_fingerprint")),
                "rules_config_hash": _safe_text(manifest.get("rules_config_hash")),
                "dataset_link": _relative_link(dataset_concept, run_concept, f"Run {run_id}"),
            }
        ),
    )

    runbook_frontmatter = _base_frontmatter(
        concept_types["runbook"],
        "Mule Account Investigation Runbook",
        "Suggested human review steps for suspicious indicators.",
        run_id,
        "fraud-demo://runbook/mule_account_investigation",
        manifest,
    )
    _write_markdown(
        bundle / f"{runbook_concept}.md",
        env.get_template("runbook.md.j2").render(
            {
                "frontmatter": _frontmatter(runbook_frontmatter),
                "run_link": _relative_link(runbook_concept, run_concept, f"Run {run_id}"),
            }
        ),
    )
    return 3


def _write_indexes(bundle: Path, config: dict[str, Any], counts: dict[str, int]) -> None:
    name = str(config.get("bundle_name", "Mule Account Fraud Knowledge Graph"))
    if config.get("include_root_version_frontmatter", False):
        root = f'---\nokf_version: "{config.get("version", "0.1")}"\n---\n\n'
    else:
        root = ""
    root += (
        f"# {name}\n\n"
        "- [Accounts](accounts/) - Suspicious accounts and bounded counterparties.\n"
        "- [Alerts](alerts/) - Explainable fraud alerts requiring review.\n"
        "- [Clusters](clusters/) - Suspicious connected account networks.\n"
        "- [Signals](signals/) - Deterministic risk-rule definitions.\n"
        "- [Runs](runs/) - Pipeline provenance.\n"
    )
    _write_markdown(bundle / "index.md", root)

    labels = {
        "accounts": "Accounts",
        "alerts": "Alerts",
        "clusters": "Clusters",
        "signals": "Signals",
        "devices": "Devices",
        "ips": "IP Addresses",
        "metrics": "Metrics",
        "runs": "Runs",
        "datasets": "Datasets",
        "runbooks": "Runbooks",
        "references": "References",
    }
    for directory in OPTIONAL_INDEX_DIRS:
        _write_markdown(
            bundle / directory / "index.md",
            f"# {labels[directory]}\n\n{counts.get(directory, 0)} generated concepts.\n",
        )

    today = datetime.now(UTC).date().isoformat()
    _write_markdown(
        bundle / "log.md",
        f"# OKF Export Log\n\n## {today}\n\n- Exported bundle from Phase 5 pipeline.\n",
    )


def _write_okf_manifest(
    bundle: Path,
    *,
    run_id: str,
    config: dict[str, Any],
    counts: dict[str, int],
    concept_count: int,
) -> Path:
    manifest_path = bundle / "okf_manifest.json"
    payload = {
        "okf_version": str(config.get("version", "0.1")),
        "bundle_path": str(bundle),
        "run_id": run_id,
        "concept_count": concept_count,
        "counts": counts,
        "generated_at": datetime.now(UTC).isoformat(),
        "human_review_required": True,
    }
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def _update_concept_ids(
    run_path: Path,
    account_map: dict[str, str],
    alert_map: dict[str, str],
) -> None:
    risk_path = run_path / "account_risk.parquet"
    alerts_path = run_path / "alerts.parquet"
    risk = pd.read_parquet(risk_path)
    alerts = pd.read_parquet(alerts_path)
    if "okf_concept_id" not in risk.columns:
        risk["okf_concept_id"] = None
    if "okf_concept_id" not in alerts.columns:
        alerts["okf_concept_id"] = None
    risk["okf_concept_id"] = risk["account_id"].astype(str).map(account_map).combine_first(
        risk["okf_concept_id"]
    )
    alerts["okf_concept_id"] = alerts["alert_id"].astype(str).map(alert_map).combine_first(
        alerts["okf_concept_id"]
    )
    risk.to_parquet(risk_path, index=False)
    alerts.to_parquet(alerts_path, index=False)
    with duckdb.connect(str(run_path / "transactions.duckdb")) as connection:
        for table_name, frame in [("account_risk", risk), ("alerts", alerts)]:
            view_name = f"{table_name}_df"
            connection.register(view_name, frame)
            connection.execute(f"create or replace table {table_name} as select * from {view_name}")
            connection.unregister(view_name)


def export_okf_bundle(
    run_dir: Path | str,
    *,
    okf_config_path: Path | str = "config/okf.yaml",
    rules_path: Path | str = "config/rules.yaml",
) -> OkfExportResult:
    """Export a bounded OKF knowledge bundle from Phase 4 run artifacts."""

    run_path = Path(run_dir)
    run_id = run_path.name
    manifest_path = run_path / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_id = str(manifest.get("run_id") or run_id)
    config = _read_yaml(okf_config_path)
    bundle = Path(str(config.get("output_dir", "artifacts/okf_bundle")))
    limits = config.get("export_limits", {})
    concept_types = config.get("concept_types", {})
    if bundle.exists():
        shutil.rmtree(bundle)
    for directory in OPTIONAL_INDEX_DIRS:
        (bundle / directory).mkdir(parents=True, exist_ok=True)

    artifacts = _required_artifacts(run_path)
    rules_config = load_rules_config(rules_path)
    enabled_rules = [
        rule_id for rule_id, rule in rules_config.rules.items() if bool(rule.enabled)
    ]
    alerts = _select_alerts(artifacts["alerts"], int(limits.get("max_alerts", 500)))
    clusters = _select_clusters(artifacts["clusters"], int(limits.get("max_clusters", 100)))
    accounts = _select_accounts(
        artifacts["account_risk"],
        alerts,
        artifacts["graph_nodes"],
        int(limits.get("max_accounts", 500)),
    )
    maps = _concept_maps(accounts, alerts, clusters, enabled_rules, run_id)
    include_relations = _relations_enabled(config)
    env = _template_env()

    counts = {directory: 0 for directory in OPTIONAL_INDEX_DIRS}
    for _, row in accounts.iterrows():
        _render_account(
            env,
            bundle,
            row,
            run_id=run_id,
            concept_id=maps["accounts"][str(row["account_id"])],
            concept_type=str(concept_types.get("account", "Fraud Account")),
            manifest=manifest,
            maps=maps,
            evidence=artifacts["rule_evidence"],
            graph_edges=artifacts["graph_edges"],
            include_relations=include_relations,
        )
        counts["accounts"] += 1

    for _, row in alerts.iterrows():
        _render_alert(
            env,
            bundle,
            row,
            run_id=run_id,
            concept_id=maps["alerts"][str(row["alert_id"])],
            concept_type=str(concept_types.get("alert", "Fraud Alert")),
            manifest=manifest,
            maps=maps,
            evidence=artifacts["rule_evidence"],
            include_relations=include_relations,
        )
        counts["alerts"] += 1

    for _, row in clusters.iterrows():
        _render_cluster(
            env,
            bundle,
            row,
            run_id=run_id,
            concept_id=maps["clusters"][str(row["cluster_id"])],
            concept_type=str(concept_types.get("cluster", "Fraud Cluster")),
            manifest=manifest,
            maps=maps,
            alerts=alerts,
            include_relations=include_relations,
        )
        counts["clusters"] += 1

    for rule_id in enabled_rules:
        _render_signal(
            env,
            bundle,
            rule_id,
            rules_config.rules[rule_id],
            run_id=run_id,
            concept_id=maps["signals"][rule_id],
            concept_type=str(concept_types.get("signal", "Fraud Signal")),
            manifest=manifest,
            maps=maps,
            include_relations=include_relations,
        )
        counts["signals"] += 1

    counts["runs"] += 1
    counts["datasets"] += 1
    counts["runbooks"] += 1
    _render_run_dataset_runbook(
        env,
        bundle,
        run_id=run_id,
        config=config,
        manifest=manifest,
        maps=maps,
        concept_types={
            "run": str(concept_types.get("run", "Fraud Pipeline Run")),
            "dataset": str(concept_types.get("dataset", "Fraud Dataset")),
            "runbook": str(concept_types.get("runbook", "Fraud Runbook")),
        },
    )

    concept_count = sum(counts.values())
    _write_indexes(bundle, config, counts)
    okf_manifest_path = _write_okf_manifest(
        bundle,
        run_id=run_id,
        config=config,
        counts=counts,
        concept_count=concept_count,
    )
    _update_concept_ids(run_path, maps["accounts"], maps["alerts"])
    return OkfExportResult(
        run_id=run_id,
        run_dir=run_path,
        bundle_path=bundle,
        okf_manifest_path=okf_manifest_path,
        concept_count=concept_count,
        account_count=counts["accounts"],
        alert_count=counts["alerts"],
        cluster_count=counts["clusters"],
    )
