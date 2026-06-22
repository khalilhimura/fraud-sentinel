"""Network explorer dashboard page placeholder."""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from dashboard.common import (
    build_network_figure,
    cluster_options,
    configure_page,
    load_artifacts_from_sidebar,
    render_artifact_health,
    render_disclaimer,
    render_empty,
    render_provenance,
    risk_options,
)
from dashboard.data import build_bounded_graph


def render_page() -> None:
    configure_page("Network Explorer")
    st.title("Network Explorer")
    artifacts = load_artifacts_from_sidebar()
    if artifacts is None or not artifacts.manifest:
        render_empty("No prepared graph artifacts are available.")
        return
    render_disclaimer()
    render_provenance(artifacts)
    render_artifact_health(artifacts)

    nodes = artifacts.frames["graph_nodes"]
    if nodes.empty:
        render_empty("No bounded graph nodes are present in the selected run.")
        return

    account_options = sorted(
        str(value)
        for value in nodes.loc[nodes["node_type"].eq("Account"), "node_id"].dropna().unique()
    )
    selected_mode = st.radio("Focus", ["Account", "Cluster"], horizontal=True)
    c1, c2, c3 = st.columns(3)
    selected_account = ""
    selected_cluster = ""
    if selected_mode == "Account":
        selected_account = c1.selectbox("Account", account_options)
    else:
        selected_cluster = c1.selectbox("Cluster", cluster_options(nodes))
    depth = c2.selectbox("Depth", [1, 2], index=0)
    min_amount = c3.number_input("Minimum amount", min_value=0.0, value=0.0, step=100.0)
    c4, c5, c6 = st.columns(3)
    min_count = c4.number_input("Minimum transaction count", min_value=0, value=0, step=1)
    selected_levels = c5.multiselect("Risk level", risk_options(nodes))
    node_types = sorted(str(value) for value in nodes["node_type"].dropna().unique())
    selected_types = c6.multiselect("Node type", node_types, default=node_types)

    graph = build_bounded_graph(
        artifacts,
        {
            "account_id": selected_account,
            "cluster_id": selected_cluster,
            "depth": depth,
            "min_amount": min_amount,
            "min_transaction_count": min_count,
            "risk_levels": selected_levels,
            "node_types": selected_types,
        },
    )
    cols = st.columns(3)
    cols[0].metric("Rendered nodes", len(graph["nodes"]))
    cols[1].metric("Rendered edges", len(graph["edges"]))
    cols[2].metric("Limit", f"{graph['limits']['max_nodes']} / {graph['limits']['max_edges']}")
    if graph["truncated"]:
        st.warning("Graph was capped before browser rendering.")
    st.plotly_chart(build_network_figure(graph), width="stretch")


if __name__ == "__main__":
    render_page()
