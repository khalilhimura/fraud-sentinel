"""Streamlit dashboard shell for Fraud Sentinel."""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from dashboard.common import (
    amount_value,
    configure_page,
    load_artifacts_from_sidebar,
    render_artifact_health,
    render_disclaimer,
    render_provenance,
)
from dashboard.data import build_overview_metrics


def render_app() -> None:
    configure_page("Run Console")
    st.title("Fraud Sentinel")
    artifacts = load_artifacts_from_sidebar()
    if artifacts is None or not artifacts.manifest:
        st.info("No prepared run manifest is available.")
        return

    render_disclaimer()
    render_provenance(artifacts)
    render_artifact_health(artifacts)

    metrics = build_overview_metrics(artifacts)
    cols = st.columns(4)
    cols[0].metric("Valid rows", f"{metrics['valid_row_count']:,}")
    cols[1].metric("Rejected rows", f"{metrics['rejected_row_count']:,}")
    cols[2].metric("High/Critical alerts", f"{metrics['high_critical_alert_count']:,}")
    cols[3].metric("Suspicious amount", amount_value(metrics["suspicious_transfer_amount"]))

    st.subheader("Review Surfaces")
    page_links = [
        ("Overview", "pages/1_Overview.py"),
        ("Alert Queue", "pages/2_Alerts.py"),
        ("Account Investigation", "pages/3_Account_Investigation.py"),
        ("Network Explorer", "pages/4_Network_Explorer.py"),
        ("OKF Knowledge Bundle", "pages/5_OKF_Knowledge_Bundle.py"),
        ("Monitoring", "pages/6_Monitoring.py"),
    ]
    for label, path in page_links:
        st.page_link(path, label=label)


if __name__ == "__main__":
    render_app()
