import streamlit as st
import os
import sys


def render_sidebar():
    """Render the shared sidebar with branding, stats, and navigation hints."""
    st.sidebar.title("RegScan")
    st.sidebar.caption("AI-Powered Regulatory Intelligence")
    st.sidebar.divider()

    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from ingestion.vector_store import RegulatoryVectorStore
        vs = RegulatoryVectorStore()
        recent = vs.list_recent(days=180)
        st.sidebar.metric("Regulations (6 months)", len(recent))
        st.sidebar.metric("Total chunks indexed", vs.count())
    except Exception:
        st.sidebar.info("Vector store not initialised.")

    st.sidebar.metric("Jurisdictions", 4)
    st.sidebar.markdown("**Sources:** NCSC · EEAS · Ofcom")
    st.sidebar.divider()
    st.sidebar.markdown(
        "_RegScan v1.0 — Colt Technology Services_"
    )
