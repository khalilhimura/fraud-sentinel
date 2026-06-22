"""Alert queue dashboard page placeholder."""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import streamlit as st

from dashboard.common import (
    cluster_options,
    configure_page,
    load_artifacts_from_sidebar,
    render_artifact_health,
    render_disclaimer,
    render_empty,
    render_provenance,
    risk_options,
    rule_options,
)
from dashboard.data import filter_alerts, prepare_alert_download


def render_page() -> None:
    configure_page("Alert Queue")
    st.title("Alert Queue")
    artifacts = load_artifacts_from_sidebar()
    if artifacts is None or not artifacts.manifest:
        render_empty("No prepared alert artifacts are available.")
        return
    render_disclaimer()
    render_provenance(artifacts)
    render_artifact_health(artifacts)

    alerts = artifacts.frames["alerts"]
    if alerts.empty:
        render_empty("No alerts are present in the selected run.")
        return

    created = alerts.get("created_at")
    min_date = max_date = None
    if created is not None:
        created_dates = list(
            sorted(
                {
                    value.date()
                    for value in pd.to_datetime(
                        created,
                        errors="coerce",
                        utc=True,
                    ).dropna()
                }
            )
        )
        if created_dates:
            min_date = created_dates[0]
            max_date = created_dates[-1]

    c1, c2, c3, c4 = st.columns(4)
    risk_levels = risk_options(alerts)
    selected_levels = c1.multiselect("Risk level", risk_levels, default=risk_levels)
    min_score = c2.slider("Minimum score", 0, 100, 0, 5)
    selected_rule = c3.selectbox("Triggered rule", ["All", *rule_options(alerts)])
    selected_cluster = c4.selectbox("Cluster", ["All", *cluster_options(alerts)])
    date_range = None
    if min_date and max_date:
        date_range = st.date_input("Created date", (min_date, max_date))

    filters = {
        "risk_levels": selected_levels,
        "min_score": min_score,
        "triggered_rule": selected_rule,
        "cluster_id": selected_cluster,
        "date_range": date_range if isinstance(date_range, tuple) else None,
    }
    filtered = filter_alerts(alerts, filters)
    st.download_button(
        "Download filtered CSV",
        data=prepare_alert_download(filtered),
        file_name="filtered_alerts.csv",
        mime="text/csv",
    )
    st.dataframe(filtered, width="stretch", hide_index=True)


if __name__ == "__main__":
    render_page()
