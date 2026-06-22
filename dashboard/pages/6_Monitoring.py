"""Monitoring dashboard page placeholder."""

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


def render_page() -> None:
    configure_page("Monitoring")
    st.title("Monitoring")
    artifacts = load_artifacts_from_sidebar()
    if artifacts is None or not artifacts.manifest:
        render_empty("No run manifest is available.")
        return
    render_disclaimer()
    render_provenance(artifacts)
    render_artifact_health(artifacts)

    manifest = artifacts.manifest
    cols = st.columns(4)
    cols[0].metric("Last run", str(manifest.get("run_id") or artifacts.run_dir.name))
    cols[1].metric("Status", str(manifest.get("status") or "unknown"))
    cols[2].metric("Rejected rows", int(manifest.get("rejected_row_count") or 0))
    cols[3].metric("Valid rows", int(manifest.get("valid_row_count") or 0))

    st.subheader("Source Files")
    st.dataframe(
        [{"source_file": value} for value in manifest.get("source_files", [])],
        width="stretch",
        hide_index=True,
    )
    st.subheader("Source Fingerprints")
    st.json(manifest.get("source_file_fingerprints") or {})
    st.subheader("Stage Timings")
    st.dataframe(
        [
            {"stage": stage, "seconds": seconds}
            for stage, seconds in (manifest.get("stage_timings_seconds") or {}).items()
        ],
        width="stretch",
        hide_index=True,
    )
    st.subheader("Artifact Paths")
    st.dataframe(
        [
            {"artifact": key, "path": value}
            for key, value in (manifest.get("artifact_paths") or {}).items()
        ],
        width="stretch",
        hide_index=True,
    )


if __name__ == "__main__":
    render_page()
