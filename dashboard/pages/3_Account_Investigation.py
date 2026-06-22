"""Account investigation dashboard page placeholder."""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from dashboard.common import (
    amount_value,
    build_network_figure,
    configure_page,
    load_artifacts_from_sidebar,
    render_artifact_health,
    render_disclaimer,
    render_empty,
    render_provenance,
)
from dashboard.data import build_account_investigation


def render_page() -> None:
    configure_page("Account Investigation")
    st.title("Account Investigation")
    artifacts = load_artifacts_from_sidebar()
    if artifacts is None or not artifacts.manifest:
        render_empty("No prepared account artifacts are available.")
        return
    render_disclaimer()
    render_provenance(artifacts)
    render_artifact_health(artifacts)

    risk = artifacts.frames["account_risk"].copy()
    if risk.empty:
        render_empty("No account risk rows are present in the selected run.")
        return
    risk["risk_score_sort"] = risk["risk_score"].astype(float)
    risk = risk.sort_values(["risk_score_sort", "account_id"], ascending=[False, True])
    account_id = st.selectbox("Account", risk["account_id"].astype(str).tolist())
    investigation = build_account_investigation(artifacts, str(account_id))
    account = investigation["account"]

    cols = st.columns(4)
    cols[0].metric("Risk score", account.get("risk_score", 0))
    cols[1].metric("Severity", str(account.get("risk_level", "Unknown")))
    cols[2].metric(
        "Incoming",
        amount_value(investigation["incoming_summary"]["total_amount"]),
    )
    cols[3].metric(
        "Outgoing",
        amount_value(investigation["outgoing_summary"]["total_amount"]),
    )

    st.subheader("Rule Evidence")
    st.dataframe(investigation["rule_evidence"], width="stretch", hide_index=True)

    left, right = st.columns(2)
    left.subheader("Top Counterparties")
    left.dataframe(investigation["top_counterparties"], width="stretch", hide_index=True)
    right.subheader("Cluster Membership")
    right.json(investigation["cluster"] or {})

    st.subheader("OKF Concept")
    st.code(investigation["okf_concept_id"] or "No OKF concept ID available.")
    if investigation["okf_path"]:
        st.caption(str(investigation["okf_path"]))

    st.subheader("Bounded Graph Evidence")
    st.plotly_chart(build_network_figure(investigation["graph"]), width="stretch")


if __name__ == "__main__":
    render_page()
