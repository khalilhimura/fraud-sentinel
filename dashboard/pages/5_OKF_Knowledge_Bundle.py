"""OKF knowledge bundle dashboard page placeholder."""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from dashboard.common import (
    configure_page,
    load_artifacts_from_sidebar,
    render_artifact_health,
    render_disclaimer,
    render_empty,
    render_provenance,
)
from dashboard.data import build_okf_summary, load_okf_markdown_preview


def _concept_options(artifacts) -> list[str]:
    options: set[str] = set()
    for frame_name in ["account_risk", "alerts"]:
        frame = artifacts.frames[frame_name]
        if "okf_concept_id" in frame.columns:
            options.update(
                str(value)
                for value in frame["okf_concept_id"].dropna().tolist()
                if str(value)
            )
    return sorted(options)


def render_page() -> None:
    configure_page("OKF Knowledge Bundle")
    st.title("OKF Knowledge Bundle")
    artifacts = load_artifacts_from_sidebar()
    if artifacts is None or not artifacts.manifest:
        render_empty("No OKF artifacts are available.")
        return
    render_disclaimer()
    render_provenance(artifacts)
    render_artifact_health(artifacts)

    summary = build_okf_summary(artifacts)
    cols = st.columns(5)
    cols[0].metric("OKF version", summary["okf_version"])
    cols[1].metric("Concepts", summary["concept_count"])
    cols[2].metric("Links", summary["link_count"])
    cols[3].metric("Warnings", summary["validation_warning_count"])
    cols[4].metric("Valid", "Yes" if summary["validation_valid"] else "No")
    st.code(summary["bundle_path"])

    st.subheader("Concept Counts")
    st.json(summary["counts"])
    if summary["validation_warnings"]:
        st.subheader("Validation Warnings")
        st.dataframe(summary["validation_warnings"], width="stretch")

    options = _concept_options(artifacts)
    if options:
        concept_id = st.selectbox("Concept", options)
        st.markdown(load_okf_markdown_preview(artifacts.okf_bundle_path, concept_id))
    else:
        render_empty("No OKF concept IDs are available in account or alert artifacts.")

    st.subheader("Open In Obsidian")
    st.markdown(
        "Open Obsidian, choose **Open folder as vault**, and select the bundle path above."
    )


if __name__ == "__main__":
    render_page()
