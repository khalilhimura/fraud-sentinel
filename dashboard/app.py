"""Streamlit dashboard shell for Fraud Sentinel."""

import streamlit as st

from dashboard.common import HUMAN_REVIEW_NOTICE

st.set_page_config(page_title="Fraud Sentinel", layout="wide")
st.title("Fraud Sentinel")
st.caption(HUMAN_REVIEW_NOTICE)
st.info("Dashboard artifact loading is scheduled for Phase 6.")

