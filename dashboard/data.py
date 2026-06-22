"""Cached artifact loading and dashboard view models."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import yaml

CACHE_TTL_SECONDS = 60

PARQUET_ARTIFACTS: dict[str, tuple[str, list[str]]] = {
    "normalized_transactions": (
        "normalized_transactions.parquet",
        [
            "transaction_id",
            "event_timestamp",
            "sender_account_id",
            "receiver_account_id",
            "amount",
            "currency",
        ],
    ),
    "rejected_rows": ("rejected_rows.parquet", []),
    "account_features": ("account_features.parquet", []),
    "account_risk": (
        "account_risk.parquet",
        [
            "run_id",
            "account_id",
            "risk_score",
            "risk_level",
            "triggered_rule_ids",
            "triggered_rule_count",
            "cluster_id",
            "okf_concept_id",
        ],
    ),
    "rule_evidence": (
        "rule_evidence.parquet",
        [
            "run_id",
            "account_id",
            "rule_id",
            "evaluation_status",
            "triggered",
            "feature_values_json",
            "thresholds_json",
            "human_explanation",
        ],
    ),
    "alerts": (
        "alerts.parquet",
        [
            "alert_id",
            "account_id",
            "risk_score",
            "risk_level",
            "triggered_rule_ids",
            "incoming_amount_7d",
            "outgoing_amount_7d",
            "unique_senders_7d",
            "unique_receivers_7d",
            "hold_time_proxy_minutes",
            "cluster_id",
            "created_at",
            "okf_concept_id",
        ],
    ),
    "graph_nodes": (
        "graph_nodes.parquet",
        [
            "run_id",
            "node_id",
            "node_type",
            "label",
            "account_id",
            "cluster_id",
            "risk_score",
            "risk_level",
            "is_suspicious",
            "is_context",
            "alert_id",
            "triggered_rule_ids",
            "component_id",
            "short_cycle_member",
            "properties_json",
        ],
    ),
    "graph_edges": (
        "graph_edges.parquet",
        [
            "run_id",
            "source_node_id",
            "target_node_id",
            "edge_type",
            "transaction_count",
            "total_amount",
            "currency",
            "first_seen_at",
            "last_seen_at",
            "sample_transaction_ids_json",
            "risk_relevance_score",
            "component_id",
            "properties_json",
        ],
    ),
    "clusters": (
        "clusters.parquet",
        [
            "run_id",
            "cluster_id",
            "component_id",
            "account_count",
            "suspicious_account_count",
            "total_transfer_amount",
            "max_risk_score",
            "member_account_ids_json",
            "suspicious_account_ids_json",
            "human_review_note",
        ],
    ),
    "alert_changes": ("alert_changes.parquet", []),
}
OPTIONAL_PARQUET_ARTIFACTS = {"account_features", "alert_changes"}

ALERT_TABLE_COLUMNS = [
    "alert_id",
    "account_id",
    "risk_score",
    "risk_level",
    "triggered_rule_ids",
    "incoming_amount_7d",
    "outgoing_amount_7d",
    "unique_senders_7d",
    "unique_receivers_7d",
    "hold_time_proxy_minutes",
    "cluster_id",
    "created_at",
    "okf_concept_id",
]

SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Context": 4}
SUSPICIOUS_LEVELS = {"high", "critical"}


@dataclass(frozen=True)
class DashboardConfig:
    """Dashboard configuration resolved from `config/dashboard.yaml`."""

    default_artifacts_dir: Path
    default_okf_bundle: Path
    cache_ttl_seconds: int
    max_nodes: int
    max_edges: int
    max_counterparties_per_account: int


@dataclass(frozen=True)
class DashboardArtifacts:
    """Loaded dashboard artifacts for one run."""

    run_dir: Path
    manifest: dict[str, Any]
    data_quality_report: dict[str, Any]
    frames: dict[str, pd.DataFrame]
    okf_manifest: dict[str, Any]
    okf_validation_report: dict[str, Any]
    missing_artifacts: tuple[str, ...]
    okf_bundle_path: Path
    config: DashboardConfig


def _empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _coerce_path(value: Any, *, fallback: Path) -> Path:
    if value is None or str(value).strip() == "":
        return fallback
    path = Path(str(value))
    return path if path.is_absolute() else path


def _resolve_artifact_path(
    manifest: dict[str, Any],
    key: str,
    run_dir: Path,
    default_name: str,
) -> Path:
    value = (manifest.get("artifact_paths") or {}).get(key)
    if value:
        path = Path(str(value))
        if path.exists() or path.is_absolute():
            return path
        cwd_relative = Path.cwd() / path
        if cwd_relative.exists():
            return cwd_relative
        return path
    return run_dir / default_name


def _json_loads(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    if hasattr(value, "tolist"):
        return value.tolist()
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    if not isinstance(value, str) or not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def as_list(value: Any) -> list[str]:
    """Return a stable string list from list-like, JSON, scalar, or missing values."""

    loaded = _json_loads(value, None)
    if isinstance(loaded, list):
        return [str(item) for item in loaded]
    if isinstance(value, (list, tuple, set)):
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


def _number(value: Any, default: float = 0.0) -> float:
    try:
        numeric = pd.to_numeric(value, errors="coerce")
    except TypeError:
        return default
    try:
        if pd.isna(numeric):
            return default
    except (TypeError, ValueError):
        return default
    return float(numeric)


def _int(value: Any, default: int = 0) -> int:
    return int(_number(value, float(default)))


def _row_dict(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {}
    return frame.iloc[0].to_dict()


def _existing_columns(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    return [column for column in columns if column in frame.columns]


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _read_yaml_cached(path: str) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _read_json_cached(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _read_parquet_cached(path: str) -> pd.DataFrame:
    return pd.read_parquet(path)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _read_markdown_cached(path: str, max_chars: int) -> str:
    return Path(path).read_text(encoding="utf-8")[:max_chars]


def load_dashboard_config(path: Path | str = "config/dashboard.yaml") -> DashboardConfig:
    """Load dashboard configuration with conservative defaults."""

    config_path = Path(path)
    data = _read_yaml_cached(str(config_path))
    limits = data.get("network_limits") or {}
    return DashboardConfig(
        default_artifacts_dir=Path(str(data.get("default_artifacts_dir", "artifacts"))),
        default_okf_bundle=Path(str(data.get("default_okf_bundle", "artifacts/okf_bundle"))),
        cache_ttl_seconds=int(data.get("cache_ttl_seconds", CACHE_TTL_SECONDS)),
        max_nodes=int(limits.get("max_nodes", 500)),
        max_edges=int(limits.get("max_edges", 5000)),
        max_counterparties_per_account=int(
            limits.get("max_counterparties_per_account", 30)
        ),
    )


def resolve_run_dir(path: Path | str, config: DashboardConfig) -> Path:
    """Resolve an artifacts directory or direct run directory to a run directory."""

    candidate = Path(path)
    if (candidate / "run_manifest.json").exists():
        return candidate
    runs_dir = candidate / "runs"
    if not runs_dir.exists() and candidate == Path("."):
        runs_dir = config.default_artifacts_dir / "runs"
    run_dirs = (
        [
            run_dir
            for run_dir in runs_dir.glob("*")
            if run_dir.is_dir() and (run_dir / "run_manifest.json").exists()
        ]
        if runs_dir.exists()
        else []
    )
    if not run_dirs:
        return candidate

    def sort_key(run_dir: Path) -> tuple[str, float, str]:
        manifest_path = run_dir / "run_manifest.json"
        completed_at = ""
        try:
            run_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            completed_at = str(run_manifest.get("completed_at") or "")
        except (OSError, json.JSONDecodeError):
            completed_at = ""
        return completed_at, manifest_path.stat().st_mtime, run_dir.name

    return sorted(run_dirs, key=sort_key)[-1]


def _load_json_artifact(path: Path, key: str, missing: list[str]) -> dict[str, Any]:
    if not path.exists():
        missing.append(key)
        return {}
    try:
        loaded = _read_json_cached(str(path))
    except (OSError, json.JSONDecodeError):
        missing.append(key)
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _load_parquet_artifact(
    path: Path,
    key: str,
    columns: list[str],
    missing: list[str],
    *,
    required: bool = True,
) -> pd.DataFrame:
    if not path.exists():
        if required:
            missing.append(key)
        return _empty_frame(columns)
    try:
        return _read_parquet_cached(str(path)).copy()
    except (OSError, ValueError):
        if required:
            missing.append(key)
        return _empty_frame(columns)


def load_dashboard_artifacts(
    run_dir: Path | str,
    config: DashboardConfig,
) -> DashboardArtifacts:
    """Load one run's prepared dashboard artifacts without touching raw CSV data."""

    resolved_run_dir = resolve_run_dir(run_dir, config)
    missing: list[str] = []
    manifest_path = resolved_run_dir / "run_manifest.json"
    manifest = _load_json_artifact(manifest_path, "run_manifest", missing)

    frames: dict[str, pd.DataFrame] = {}
    for key, (default_name, columns) in PARQUET_ARTIFACTS.items():
        path = _resolve_artifact_path(manifest, key, resolved_run_dir, default_name)
        frames[key] = _load_parquet_artifact(
            path,
            key,
            columns,
            missing,
            required=key not in OPTIONAL_PARQUET_ARTIFACTS,
        )

    data_quality_path = _resolve_artifact_path(
        manifest,
        "data_quality_report",
        resolved_run_dir,
        "data_quality_report.json",
    )
    data_quality_report = _load_json_artifact(
        data_quality_path,
        "data_quality_report",
        missing,
    )

    okf_bundle_value = (manifest.get("artifact_paths") or {}).get("okf_bundle")
    okf_bundle_path = _coerce_path(okf_bundle_value, fallback=config.default_okf_bundle)
    okf_manifest_path = _resolve_artifact_path(
        manifest,
        "okf_manifest",
        okf_bundle_path,
        "okf_manifest.json",
    )
    okf_manifest = _load_json_artifact(okf_manifest_path, "okf_manifest", missing)
    validation_report_path = _resolve_artifact_path(
        manifest,
        "okf_validation_report",
        resolved_run_dir,
        "okf_validation_report.json",
    )
    okf_validation_report = _load_json_artifact(
        validation_report_path,
        "okf_validation_report",
        missing,
    )

    return DashboardArtifacts(
        run_dir=resolved_run_dir,
        manifest=manifest,
        data_quality_report=data_quality_report,
        frames=frames,
        okf_manifest=okf_manifest,
        okf_validation_report=okf_validation_report,
        missing_artifacts=tuple(dict.fromkeys(missing)),
        okf_bundle_path=okf_bundle_path,
        config=config,
    )


def _risk_distribution(risk: pd.DataFrame) -> pd.DataFrame:
    if risk.empty or "risk_level" not in risk.columns:
        return pd.DataFrame(columns=["risk_level", "account_count"])
    counts = risk["risk_level"].fillna("Unknown").astype(str).value_counts().reset_index()
    counts.columns = ["risk_level", "account_count"]
    counts["severity_order"] = counts["risk_level"].map(SEVERITY_ORDER).fillna(99)
    return counts.sort_values(["severity_order", "risk_level"]).drop(columns=["severity_order"])


def _alerts_over_time(alerts: pd.DataFrame) -> pd.DataFrame:
    if alerts.empty or "created_at" not in alerts.columns:
        return pd.DataFrame(columns=["created_date", "alert_count"])
    frame = alerts.copy()
    frame["created_date"] = pd.to_datetime(frame["created_at"], errors="coerce", utc=True).dt.date
    frame = frame.dropna(subset=["created_date"])
    if frame.empty:
        return pd.DataFrame(columns=["created_date", "alert_count"])
    return (
        frame.groupby("created_date", as_index=False)
        .size()
        .rename(columns={"size": "alert_count"})
    )


def _top_suspicious_accounts(risk: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    if risk.empty:
        return risk.head(0).copy()
    frame = risk.copy()
    frame["risk_score"] = pd.to_numeric(frame.get("risk_score"), errors="coerce").fillna(0)
    if "risk_level" in frame.columns:
        frame = frame.loc[frame["risk_level"].astype(str).str.lower().isin(SUSPICIOUS_LEVELS)]
    return frame.sort_values(["risk_score", "account_id"], ascending=[False, True]).head(limit)


def _top_triggered_rules(alerts: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    if alerts.empty or "triggered_rule_ids" not in alerts.columns:
        return pd.DataFrame(columns=["rule_id", "alert_count"])
    counts: dict[str, int] = {}
    for value in alerts["triggered_rule_ids"].tolist():
        for rule_id in as_list(value):
            counts[rule_id] = counts.get(rule_id, 0) + 1
    return (
        pd.DataFrame(
            [{"rule_id": rule_id, "alert_count": count} for rule_id, count in counts.items()]
        )
        .sort_values(["alert_count", "rule_id"], ascending=[False, True])
        .head(limit)
        if counts
        else pd.DataFrame(columns=["rule_id", "alert_count"])
    )


def build_overview_metrics(artifacts: DashboardArtifacts) -> dict[str, object]:
    """Build top-level dashboard metrics from prepared artifacts."""

    manifest = artifacts.manifest
    alerts = artifacts.frames["alerts"]
    risk = artifacts.frames["account_risk"]
    clusters = artifacts.frames["clusters"]
    suspicious_alerts = (
        alerts.loc[
            alerts.get("risk_level", pd.Series(dtype=str))
            .astype(str)
            .str.lower()
            .isin(SUSPICIOUS_LEVELS)
        ]
        if not alerts.empty
        else alerts
    )
    suspicious_transfer_amount = 0.0
    if not clusters.empty and "total_transfer_amount" in clusters.columns:
        suspicious_transfer_amount = float(
            pd.to_numeric(clusters["total_transfer_amount"], errors="coerce").fillna(0).sum()
        )
    valid_rows = len(artifacts.frames["normalized_transactions"])
    rejected_rows = len(artifacts.frames["rejected_rows"])
    return {
        "valid_row_count": int(manifest.get("valid_row_count", valid_rows) or 0),
        "rejected_row_count": int(manifest.get("rejected_row_count", rejected_rows) or 0),
        "distinct_account_count": int(manifest.get("distinct_account_count", 0) or 0),
        "alert_count": int(manifest.get("alert_count", len(alerts)) or 0),
        "high_critical_alert_count": int(len(suspicious_alerts)),
        "suspicious_cluster_count": int(manifest.get("cluster_count", len(clusters)) or 0),
        "suspicious_transfer_amount": suspicious_transfer_amount,
        "run_id": str(manifest.get("run_id") or artifacts.run_dir.name),
        "source_data_fingerprint": str(manifest.get("source_data_fingerprint") or ""),
        "risk_distribution": _risk_distribution(risk),
        "alerts_over_time": _alerts_over_time(alerts),
        "top_suspicious_accounts": _top_suspicious_accounts(risk),
        "top_triggered_rules": _top_triggered_rules(alerts),
    }


def filter_alerts(alerts: pd.DataFrame, filters: dict[str, object]) -> pd.DataFrame:
    """Filter alert rows using analyst-facing controls."""

    if alerts.empty:
        return alerts.copy()
    frame = alerts.copy()
    if filters.get("risk_levels"):
        levels = {str(level).lower() for level in filters["risk_levels"] or []}
        frame = frame.loc[frame["risk_level"].astype(str).str.lower().isin(levels)]
    if filters.get("min_score") is not None:
        frame = frame.loc[
            pd.to_numeric(frame.get("risk_score"), errors="coerce").fillna(0)
            >= float(filters["min_score"] or 0)
        ]
    triggered_rule = str(filters.get("triggered_rule") or "")
    if triggered_rule and triggered_rule.lower() != "all":
        frame = frame.loc[
            frame.get("triggered_rule_ids", pd.Series(dtype=object)).apply(
                lambda value: triggered_rule in as_list(value)
            )
        ]
    cluster_id = str(filters.get("cluster_id") or "")
    if cluster_id and cluster_id.lower() != "all" and "cluster_id" in frame.columns:
        frame = frame.loc[frame["cluster_id"].astype(str).eq(cluster_id)]
    date_range = filters.get("date_range")
    if date_range and "created_at" in frame.columns:
        start, end = date_range  # type: ignore[misc]
        created = pd.to_datetime(frame["created_at"], errors="coerce", utc=True)
        if start:
            frame = frame.loc[created >= pd.Timestamp(start, tz="UTC")]
            created = created.loc[frame.index]
        if end:
            end_exclusive = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
            frame = frame.loc[created < end_exclusive]
    for optional_column in ["country", "bank", "channel"]:
        selected = filters.get(optional_column)
        if selected and optional_column in frame.columns and str(selected).lower() != "all":
            frame = frame.loc[frame[optional_column].astype(str).eq(str(selected))]
    columns = [*_existing_columns(frame, ALERT_TABLE_COLUMNS)]
    columns.extend(column for column in frame.columns if column not in columns)
    return frame.loc[:, columns].reset_index(drop=True)


def prepare_alert_download(alerts: pd.DataFrame) -> bytes:
    """Return a CSV payload for the filtered alert table."""

    columns = [*_existing_columns(alerts, ALERT_TABLE_COLUMNS)]
    columns.extend(column for column in alerts.columns if column not in columns)
    return alerts.loc[:, columns].to_csv(index=False).encode("utf-8")


def _edge_summary(edges: pd.DataFrame) -> dict[str, float | int]:
    if edges.empty:
        return {"transaction_count": 0, "total_amount": 0.0, "edge_count": 0}
    return {
        "transaction_count": int(
            pd.to_numeric(edges.get("transaction_count"), errors="coerce").fillna(0).sum()
        ),
        "total_amount": float(
            pd.to_numeric(edges.get("total_amount"), errors="coerce").fillna(0).sum()
        ),
        "edge_count": int(len(edges)),
    }


def _top_counterparties(edges: pd.DataFrame, account_id: str, limit: int) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for row in edges.itertuples(index=False):
        source = str(row.source_node_id)
        target = str(row.target_node_id)
        if source == account_id:
            node_id = target
            direction = "outgoing"
        elif target == account_id:
            node_id = source
            direction = "incoming"
        else:
            continue
        records.append(
            {
                "node_id": node_id,
                "direction": direction,
                "transaction_count": int(row.transaction_count),
                "total_amount": float(row.total_amount),
                "first_seen_at": row.first_seen_at,
                "last_seen_at": row.last_seen_at,
            }
        )
    if not records:
        return pd.DataFrame(
            columns=[
                "node_id",
                "direction",
                "transaction_count",
                "total_amount",
                "first_seen_at",
                "last_seen_at",
            ]
        )
    return (
        pd.DataFrame(records)
        .sort_values(
            ["total_amount", "transaction_count", "node_id"],
            ascending=[False, False, True],
        )
        .head(limit)
        .reset_index(drop=True)
    )


def build_account_investigation(
    artifacts: DashboardArtifacts,
    account_id: str,
) -> dict[str, object]:
    """Join prepared artifacts for a selected account investigation."""

    risk = artifacts.frames["account_risk"]
    evidence = artifacts.frames["rule_evidence"]
    alerts = artifacts.frames["alerts"]
    edges = artifacts.frames["graph_edges"]
    clusters = artifacts.frames["clusters"]

    account_rows = risk.loc[
        risk.get("account_id", pd.Series(dtype=str)).astype(str).eq(account_id)
    ]
    account = _row_dict(account_rows)
    evidence_rows = evidence.loc[
        evidence.get("account_id", pd.Series(dtype=str)).astype(str).eq(account_id)
        & evidence.get("evaluation_status", pd.Series(dtype=str)).astype(str).eq("triggered")
    ].copy()
    alert_rows = alerts.loc[
        alerts.get("account_id", pd.Series(dtype=str)).astype(str).eq(account_id)
    ].copy()
    transfer_edges = edges.loc[
        edges.get("edge_type", pd.Series(dtype=str)).eq("TRANSFERRED_TO")
    ].copy()
    incoming = transfer_edges.loc[
        transfer_edges.get("target_node_id", pd.Series(dtype=str))
        .astype(str)
        .eq(account_id)
    ]
    outgoing = transfer_edges.loc[
        transfer_edges.get("source_node_id", pd.Series(dtype=str))
        .astype(str)
        .eq(account_id)
    ]

    cluster_id = str(account.get("cluster_id") or "")
    cluster_rows = (
        clusters.loc[clusters.get("cluster_id", pd.Series(dtype=str)).astype(str).eq(cluster_id)]
        if cluster_id
        else clusters.head(0)
    )
    okf_concept_id = str(account.get("okf_concept_id") or "")
    okf_path = artifacts.okf_bundle_path / f"{okf_concept_id}.md" if okf_concept_id else None

    return {
        "account": account,
        "alerts": alert_rows.reset_index(drop=True),
        "rule_evidence": evidence_rows.reset_index(drop=True),
        "incoming_summary": _edge_summary(incoming),
        "outgoing_summary": _edge_summary(outgoing),
        "top_counterparties": _top_counterparties(
            transfer_edges,
            account_id,
            artifacts.config.max_counterparties_per_account,
        ),
        "graph": build_bounded_graph(artifacts, {"account_id": account_id, "depth": 1}),
        "cluster": _row_dict(cluster_rows),
        "okf_concept_id": okf_concept_id,
        "okf_path": str(okf_path) if okf_path is not None else "",
    }


def _selected_node_ids(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    filters: dict[str, object],
) -> set[str]:
    account_id = str(filters.get("account_id") or "")
    cluster_id = str(filters.get("cluster_id") or "")
    if cluster_id:
        cluster_nodes = nodes.loc[
            nodes.get("cluster_id", pd.Series(dtype=str)).astype(str).eq(cluster_id)
            | nodes.get("node_id", pd.Series(dtype=str)).astype(str).eq(cluster_id)
        ]
        return {
            str(value)
            for value in cluster_nodes.get("node_id", pd.Series(dtype=str)).tolist()
        }
    if not account_id:
        return {str(value) for value in nodes.get("node_id", pd.Series(dtype=str)).tolist()}

    selected = {account_id}
    depth = max(min(_int(filters.get("depth"), 1), 2), 1)
    transfer_edges = edges.loc[
        edges.get("edge_type", pd.Series(dtype=str)).isin(
            ["TRANSFERRED_TO", "MEMBER_OF_CLUSTER"]
        )
    ]
    frontier = {account_id}
    for _ in range(depth):
        next_frontier: set[str] = set()
        for row in transfer_edges.itertuples(index=False):
            source = str(row.source_node_id)
            target = str(row.target_node_id)
            if source in frontier and target not in selected:
                next_frontier.add(target)
            if target in frontier and source not in selected:
                next_frontier.add(source)
        selected.update(next_frontier)
        frontier = next_frontier
        if not frontier:
            break
    return selected


def _sort_nodes_for_graph(nodes: pd.DataFrame) -> pd.DataFrame:
    if nodes.empty:
        return nodes
    frame = nodes.copy()
    frame["risk_score_sort"] = pd.to_numeric(frame.get("risk_score"), errors="coerce").fillna(0)
    frame["is_suspicious_sort"] = frame.get("is_suspicious", False).fillna(False).astype(bool)
    frame["severity_order"] = frame.get("risk_level", "").map(SEVERITY_ORDER).fillna(99)
    return frame.sort_values(
        ["is_suspicious_sort", "risk_score_sort", "severity_order", "node_id"],
        ascending=[False, False, True, True],
    )


def _sort_edges_for_graph(edges: pd.DataFrame) -> pd.DataFrame:
    if edges.empty:
        return edges
    frame = edges.copy()
    frame["amount_sort"] = pd.to_numeric(frame.get("total_amount"), errors="coerce").fillna(0)
    frame["count_sort"] = pd.to_numeric(frame.get("transaction_count"), errors="coerce").fillna(0)
    frame["risk_sort"] = pd.to_numeric(frame.get("risk_relevance_score"), errors="coerce").fillna(0)
    return frame.sort_values(
        ["risk_sort", "amount_sort", "count_sort", "source_node_id", "target_node_id"],
        ascending=[False, False, False, True, True],
    )


def build_bounded_graph(
    artifacts: DashboardArtifacts,
    filters: dict[str, object],
) -> dict[str, object]:
    """Return graph nodes and edges after applying filters and configured caps."""

    nodes = artifacts.frames["graph_nodes"].copy()
    edges = artifacts.frames["graph_edges"].copy()
    if nodes.empty:
        return {
            "nodes": [],
            "edges": [],
            "limits": {
                "max_nodes": artifacts.config.max_nodes,
                "max_edges": artifacts.config.max_edges,
            },
            "truncated": False,
        }
    if not edges.empty:
        if filters.get("min_amount") is not None:
            amount = pd.to_numeric(
                edges.get("total_amount"),
                errors="coerce",
            ).fillna(0)
            edges = edges.loc[amount >= float(filters.get("min_amount") or 0)]
        if filters.get("min_transaction_count") is not None:
            count = pd.to_numeric(
                edges.get("transaction_count"),
                errors="coerce",
            ).fillna(0)
            min_count = float(filters.get("min_transaction_count") or 0)
            edges = edges.loc[count >= min_count]

    selected_ids = _selected_node_ids(nodes, edges, filters)
    nodes = nodes.loc[
        nodes.get("node_id", pd.Series(dtype=str)).astype(str).isin(selected_ids)
    ]
    if filters.get("risk_levels"):
        levels = {str(level).lower() for level in filters.get("risk_levels") or []}
        nodes = nodes.loc[
            nodes.get("risk_level", pd.Series(dtype=str))
            .astype(str)
            .str.lower()
            .isin(levels)
        ]
    if filters.get("node_types"):
        node_types = {str(node_type) for node_type in filters.get("node_types") or []}
        nodes = nodes.loc[nodes.get("node_type", pd.Series(dtype=str)).astype(str).isin(node_types)]
    nodes = _sort_nodes_for_graph(nodes)
    original_node_count = len(nodes)
    nodes = nodes.head(artifacts.config.max_nodes)
    allowed_ids = {str(value) for value in nodes.get("node_id", pd.Series(dtype=str)).tolist()}

    if not edges.empty:
        edges = edges.loc[
            edges.get("source_node_id", pd.Series(dtype=str)).astype(str).isin(allowed_ids)
            & edges.get("target_node_id", pd.Series(dtype=str)).astype(str).isin(allowed_ids)
        ]
    edges = _sort_edges_for_graph(edges)
    original_edge_count = len(edges)
    edges = edges.head(artifacts.config.max_edges)
    return {
        "nodes": nodes.drop(
            columns=["risk_score_sort", "is_suspicious_sort", "severity_order"],
            errors="ignore",
        ).to_dict(orient="records"),
        "edges": edges.drop(
            columns=["amount_sort", "count_sort", "risk_sort"],
            errors="ignore",
        ).to_dict(orient="records"),
        "limits": {
            "max_nodes": artifacts.config.max_nodes,
            "max_edges": artifacts.config.max_edges,
        },
        "truncated": original_node_count > len(nodes) or original_edge_count > len(edges),
    }


def build_okf_summary(artifacts: DashboardArtifacts) -> dict[str, object]:
    """Summarize OKF manifest and validation report for dashboard display."""

    validation = artifacts.okf_validation_report
    manifest = artifacts.okf_manifest
    return {
        "okf_version": str(
            validation.get("okf_version") or manifest.get("okf_version") or "0.1"
        ),
        "concept_count": int(
            validation.get("concept_count", manifest.get("concept_count", 0)) or 0
        ),
        "counts": manifest.get("counts") or {},
        "link_count": int(validation.get("link_count", 0) or 0),
        "validation_valid": bool(validation.get("valid", False)),
        "validation_warning_count": len(validation.get("warnings") or []),
        "validation_warnings": validation.get("warnings") or [],
        "hard_errors": validation.get("hard_errors") or [],
        "bundle_path": str(artifacts.okf_bundle_path),
    }


def load_okf_markdown_preview(
    bundle: Path | str,
    concept_id: str,
    max_chars: int = 12_000,
) -> str:
    """Load a bounded Markdown preview for an OKF concept path."""

    bundle_path = Path(bundle).resolve()
    concept_path = Path(concept_id)
    if concept_path.suffix != ".md":
        concept_path = concept_path.with_suffix(".md")
    path = (bundle_path / concept_path).resolve()
    try:
        path.relative_to(bundle_path)
    except ValueError:
        return "Concept path escapes the OKF bundle."
    if not path.exists():
        return f"Concept Markdown not found: {concept_id}"
    return _read_markdown_cached(str(path), int(max_chars))
