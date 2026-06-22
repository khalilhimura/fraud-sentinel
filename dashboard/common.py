"""Shared dashboard rendering helpers."""

from __future__ import annotations

from html import escape
from typing import Any

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.data import (
    DashboardArtifacts,
    build_overview_metrics,
    load_dashboard_artifacts,
    load_dashboard_config,
)

HUMAN_REVIEW_NOTICE = (
    "Suspicious indicators require human review and are not confirmed fraud judgments."
)

SEVERITY_COLORS = {
    "Critical": "#B42318",
    "High": "#B87913",
    "Medium": "#4F6F52",
    "Low": "#60717A",
    "Context": "#7A858B",
}


def configure_page(title: str) -> None:
    """Apply Streamlit page config and compact dashboard styling."""

    st.set_page_config(page_title=f"Fraud Sentinel | {title}", layout="wide")
    st.markdown(
        """
        <style>
        .stApp { background: #F7F8F5; color: #172026; }
        [data-testid="stAppViewContainer"] h1,
        [data-testid="stAppViewContainer"] h2,
        [data-testid="stAppViewContainer"] h3,
        [data-testid="stAppViewContainer"] label,
        [data-testid="stAppViewContainer"] p {
            color: #172026;
        }
        div[data-testid="stMetric"] {
            border: 1px solid #D7DED8;
            border-radius: 6px;
            padding: 0.75rem 0.85rem;
            background: rgba(255,255,255,0.72);
        }
        div[data-testid="stMetric"] * {
            color: #172026 !important;
        }
        .fs-provenance-card {
            border: 1px solid #D7DED8;
            border-radius: 6px;
            padding: 0.75rem 0.85rem;
            min-height: 6rem;
            background: rgba(255,255,255,0.72);
        }
        .fs-provenance-label {
            color: #172026 !important;
            font-size: 0.85rem;
            line-height: 1.2;
            margin-bottom: 0.55rem;
        }
        .fs-provenance-value {
            color: #172026 !important;
            font-size: 1.05rem;
            line-height: 1.25;
            overflow-wrap: anywhere;
            word-break: normal;
        }
        div[data-testid="stAlert"] {
            background: #FFF4CF;
            border: 1px solid #E2C16D;
            color: #172026;
        }
        div[data-testid="stAlert"] * {
            color: #172026 !important;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid #D7DED8;
            border-radius: 6px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_artifacts_from_sidebar() -> DashboardArtifacts | None:
    """Load the selected run artifacts from sidebar controls."""

    config_path = st.sidebar.text_input("Config", "config/dashboard.yaml")
    try:
        config = load_dashboard_config(config_path)
    except Exception as exc:  # pragma: no cover - defensive UI path
        st.error(f"Could not load dashboard config: {exc}")
        return None
    source = st.sidebar.text_input("Artifacts or run directory", str(config.default_artifacts_dir))
    try:
        artifacts = load_dashboard_artifacts(source, config)
    except Exception as exc:  # pragma: no cover - defensive UI path
        st.error(f"Could not load dashboard artifacts: {exc}")
        return None
    return artifacts


def render_disclaimer() -> None:
    st.warning(HUMAN_REVIEW_NOTICE)


def render_artifact_health(artifacts: DashboardArtifacts) -> None:
    if artifacts.missing_artifacts:
        st.warning("Missing prepared artifact(s): " + ", ".join(artifacts.missing_artifacts))


def render_provenance(artifacts: DashboardArtifacts) -> None:
    metrics = build_overview_metrics(artifacts)
    cols = st.columns([1.2, 2.2, 1.2, 1.2])
    values = [
        ("Run", str(metrics["run_id"])),
        ("Source fingerprint", str(metrics["source_data_fingerprint"])),
        ("Alerts", metric_value(metrics["alert_count"])),
        ("Clusters", metric_value(metrics["suspicious_cluster_count"])),
    ]
    for column, (label, value) in zip(cols, values, strict=True):
        column.markdown(
            (
                '<div class="fs-provenance-card">'
                f'<div class="fs-provenance-label">{escape(label)}</div>'
                f'<div class="fs-provenance-value">{escape(value)}</div>'
                "</div>"
            ),
            unsafe_allow_html=True,
        )


def metric_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def amount_value(value: Any) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def render_empty(message: str) -> None:
    st.info(message)


def risk_options(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "risk_level" not in frame.columns:
        return []
    values = sorted(str(value) for value in frame["risk_level"].dropna().unique())
    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Context": 4}
    return sorted(values, key=lambda item: (order.get(item, 99), item))


def rule_options(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "triggered_rule_ids" not in frame.columns:
        return []
    from dashboard.data import as_list

    rules: set[str] = set()
    for value in frame["triggered_rule_ids"].tolist():
        rules.update(as_list(value))
    return sorted(rules)


def cluster_options(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "cluster_id" not in frame.columns:
        return []
    return sorted(
        str(value)
        for value in frame["cluster_id"].dropna().unique()
        if str(value) and str(value).lower() != "none"
    )


def build_network_figure(graph: dict[str, object]) -> go.Figure:
    """Build a Plotly figure from already-bounded graph dictionaries."""

    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    figure = go.Figure()
    if not nodes:
        figure.update_layout(height=420, margin=dict(l=0, r=0, t=20, b=0))
        return figure

    graph_model = nx.Graph()
    for node in nodes:
        graph_model.add_node(str(node["node_id"]))
    for edge in edges:
        source = str(edge["source_node_id"])
        target = str(edge["target_node_id"])
        if source in graph_model and target in graph_model:
            graph_model.add_edge(source, target)

    positions = nx.spring_layout(graph_model, seed=42) if graph_model.nodes else {}
    for edge in edges:
        source = str(edge["source_node_id"])
        target = str(edge["target_node_id"])
        if source not in positions or target not in positions:
            continue
        x0, y0 = positions[source]
        x1, y1 = positions[target]
        amount = float(edge.get("total_amount") or 0)
        count = int(edge.get("transaction_count") or 0)
        width = max(1.0, min(8.0, 1.0 + amount / 1000.0 + count / 2.0))
        figure.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(width=width, color="#7A858B"),
                hoverinfo="text",
                text=(
                    f"{source} -> {target}<br>"
                    f"Amount: {amount:,.2f}<br>"
                    f"Transactions: {count}<br>"
                    f"{edge.get('first_seen_at', '')} to {edge.get('last_seen_at', '')}"
                ),
                showlegend=False,
            )
        )

    node_x: list[float] = []
    node_y: list[float] = []
    text: list[str] = []
    sizes: list[float] = []
    colors: list[str] = []
    degrees = dict(graph_model.degree())
    for node in nodes:
        node_id = str(node["node_id"])
        x, y = positions.get(node_id, (0.0, 0.0))
        risk_score = float(node.get("risk_score") or 0)
        risk_level = str(node.get("risk_level") or "Context")
        node_x.append(x)
        node_y.append(y)
        sizes.append(max(12.0, min(44.0, 12.0 + risk_score / 4.0 + degrees.get(node_id, 0) * 2)))
        colors.append(SEVERITY_COLORS.get(risk_level, "#60717A"))
        text.append(
            f"{node_id}<br>{node.get('node_type', '')}<br>"
            f"Risk: {risk_score:g} / {risk_level}<br>"
            f"Cluster: {node.get('cluster_id', '')}"
        )

    figure.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=[str(node["node_id"]) for node in nodes],
            textposition="top center",
            hovertext=text,
            hoverinfo="text",
            marker=dict(size=sizes, color=colors, line=dict(width=1, color="#172026")),
            showlegend=False,
        )
    )
    figure.update_layout(
        height=560,
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        plot_bgcolor="#F7F8F5",
        paper_bgcolor="#F7F8F5",
    )
    return figure
