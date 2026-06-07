from dotenv import load_dotenv
load_dotenv()

# Disable SSL verification globally for corporate proxy environment
import httpx as _httpx, warnings
_orig_client_init = _httpx.Client.__init__
_orig_async_init  = _httpx.AsyncClient.__init__
def _client_no_verify(self, *a, **kw):  kw.setdefault("verify", False); _orig_client_init(self, *a, **kw)
def _async_no_verify(self, *a, **kw):   kw.setdefault("verify", False); _orig_async_init(self, *a, **kw)
_httpx.Client.__init__      = _client_no_verify
_httpx.AsyncClient.__init__ = _async_no_verify
warnings.filterwarnings("ignore", message=".*verify.*")

import streamlit as st

st.set_page_config(
    page_title="RegScan — Regulatory Intelligence",
    page_icon="⚖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.title("RegScan")
st.sidebar.caption("AI-Powered Regulatory Intelligence")
st.sidebar.divider()

# Quick stats
try:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from ingestion.vector_store import RegulatoryVectorStore
    vs = RegulatoryVectorStore()
    recent = vs.list_recent(days=180)
    total_chunks = vs.count()
    st.sidebar.metric("Regulations (6 months)", len(recent))
    st.sidebar.metric("Total indexed chunks", total_chunks)
except Exception:
    st.sidebar.info("Vector store not yet initialised. Run the scraper first.")

st.sidebar.metric("Jurisdictions Covered", 4)
st.sidebar.markdown("**Sources:** NCSC · EEAS · Ofcom")

# Landing page
st.title("RegScan — AI Regulatory Intelligence Platform")
st.markdown(
    """
    Welcome to **RegScan**, an AI-powered regulatory monitoring and Q&A system.

    ### Features
    | Page | Description |
    |------|-------------|
    | **Chatbot** | Ask natural-language regulatory questions backed by RAG |
    | **Register** | Browse and search the live Compliance Obligation Register |
    | **Alerts** | View alert history and configure notification settings |
    | **Jurisdictions** | Multi-jurisdictional impact map |

    ### Quick Start
    1. Set your `OPENAI_API_KEY` in `.env`
    2. Run `python -m scraper.scheduler` to populate the vector store
    3. Navigate to the **Chatbot** page to start querying

    ---
    *Monitoring: NCSC (UK) · EEAS (EU Sanctions) · Ofcom (UK)*
    """
)
