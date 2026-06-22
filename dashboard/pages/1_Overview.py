"""Executive overview dashboard page placeholder."""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import plotly.express as px
import streamlit as st

from dashboard.common import (
    amount_value,
    configure_page,
    load_artifacts_from_sidebar,
    render_artifact_health,
    render_disclaimer,
    render_empty,
    render_provenance,
)
from dashboard.data import build_overview_metrics


def render_page() -> None:
    configure_page("Overview")
    st.title("Overview")
    artifacts = load_artifacts_from_sidebar()
    if artifacts is None or not artifacts.manifest:
        render_empty("No prepared run manifest is available.")
        return
    render_disclaimer()
    render_provenance(artifacts)
    render_artifact_health(artifacts)

    metrics = build_overview_metrics(artifacts)
    cols = st.columns(6)
    cols[0].metric("Valid rows", f"{metrics['valid_row_count']:,}")
    cols[1].metric("Rejected rows", f"{metrics['rejected_row_count']:,}")
    cols[2].metric("Distinct accounts", f"{metrics['distinct_account_count']:,}")
    cols[3].metric("High/Critical alerts", f"{metrics['high_critical_alert_count']:,}")
    cols[4].metric("Clusters", f"{metrics['suspicious_cluster_count']:,}")
    cols[5].metric("Suspicious amount", amount_value(metrics["suspicious_transfer_amount"]))

    left, right = st.columns(2)
    risk_distribution = metrics["risk_distribution"]
    if not risk_distribution.empty:
        left.plotly_chart(
            px.bar(
                risk_distribution,
                x="risk_level",
                y="account_count",
                color="risk_level",
                color_discrete_map={
                    "Critical": "#B42318",
                    "High": "#B87913",
                    "Medium": "#4F6F52",
                    "Low": "#60717A",
                    "Context": "#7A858B",
                },
                title="Risk Distribution",
            ),
            width="stretch",
        )
    else:
        left.info("No risk distribution is available.")

    alerts_over_time = metrics["alerts_over_time"]
    if not alerts_over_time.empty:
        right.plotly_chart(
            px.bar(
                alerts_over_time,
                x="created_date",
                y="alert_count",
                title="Alerts Over Time",
                color_discrete_sequence=["#0E7C7B"],
            ),
            width="stretch",
        )
    else:
        right.info("No alert timeline is available.")

    st.subheader("Top Suspicious Accounts")
    st.dataframe(metrics["top_suspicious_accounts"], width="stretch")
    st.subheader("Top Triggered Rules")
    st.dataframe(metrics["top_triggered_rules"], width="stretch")


if __name__ == "__main__":
    render_page()
