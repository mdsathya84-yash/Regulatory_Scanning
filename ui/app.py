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
warnings.filterwarnings("ignore")

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st

st.set_page_config(
    page_title="RegScan — Regulatory Intelligence",
    page_icon="⚖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── explicit navigation — only listed pages appear in the sidebar ─────────────
_dir = os.path.join(os.path.dirname(__file__), "pages")

pg = st.navigation(
    {
        "RegScan": [
            st.Page(os.path.join(_dir, "00_home.py"),     title="Home",     icon="🏠"),
        ],
        "Tools": [
            st.Page(os.path.join(_dir, "01_chatbot.py"),  title="Chatbot",  icon="💬"),
            st.Page(os.path.join(_dir, "02_register.py"), title="Register", icon="📋"),
        ],
    },
    position="sidebar",
)

# ── sidebar stats (shown on every page) ───────────────────────────────────────
st.sidebar.title("RegScan")
st.sidebar.caption("AI-Powered Regulatory Intelligence")
st.sidebar.divider()

try:
    from ingestion.vector_store import RegulatoryVectorStore
    vs = RegulatoryVectorStore()
    recent = vs.list_recent(days=180)
    st.sidebar.metric("Regulations (6 months)", len(recent))
    st.sidebar.metric("Total indexed chunks", vs.count())
except Exception:
    st.sidebar.info("Vector store not initialised yet.")

st.sidebar.metric("Jurisdictions Covered", 2)
st.sidebar.markdown("**Sources:** NCSC · EEAS · Ofcom · EC")

pg.run()
