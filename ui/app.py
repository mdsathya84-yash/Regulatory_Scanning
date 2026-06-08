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
from pathlib import Path

_root = Path(__file__).resolve().parent.parent   # d:\regulatory-scanner
sys.path.insert(0, str(_root))

# Resolve data paths to absolute so pages work regardless of launch CWD
def _abs(env_key: str, rel_default: str) -> str:
    val = os.environ.get(env_key, "")
    if not val or not os.path.isabs(val):
        return str(_root / rel_default)
    return val

os.environ["CHROMA_DB_PATH"]    = _abs("CHROMA_DB_PATH",    "data/chroma_db")
os.environ["REGISTER_DB_PATH"]  = _abs("REGISTER_DB_PATH",  "data/compliance_register.db")

import streamlit as st

st.set_page_config(
    page_title="RegScan — Regulatory Intelligence",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Resolve pages directory relative to this file — works regardless of CWD
_pages = Path(__file__).resolve().parent / "pages"

pg = st.navigation(
    {
        "RegScan": [
            st.Page(str(_pages / "00_home.py"),     title="Home",     icon="🏠"),
        ],
        "Tools": [
            st.Page(str(_pages / "01_chatbot.py"),  title="Chatbot",  icon="💬"),
            st.Page(str(_pages / "02_register.py"), title="Register", icon="📋"),
        ],
    },
    position="sidebar",
)

# ── sidebar — shown on every page ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚖️ RegScan")
    st.caption("AI-Powered Regulatory Intelligence")
    st.divider()

    try:
        from ingestion.vector_store import RegulatoryVectorStore
        from register.obligation_register import ObligationRegister

        vs    = RegulatoryVectorStore()
        reg   = ObligationRegister()
        stats = reg.stats()

        col_a, col_b = st.columns(2)
        col_a.metric("📄 Chunks",       f"{vs.count():,}")
        col_b.metric("📋 Obligations",  f"{stats['total']:,}")

        col_c, col_d = st.columns(2)
        col_c.metric("🔴 High Risk",    stats.get("by_risk", {}).get("HIGH", 0))
        col_d.metric("🌍 EU / 🇬🇧 UK",
                     f"{stats['by_jurisdiction'].get('EU',0)} / {stats['by_jurisdiction'].get('UK',0)}")
    except Exception:
        st.info("Vector store not initialised yet.")

    st.divider()
    st.markdown(
        "**Sources monitored**\n\n"
        "🇬🇧 NCSC &nbsp;·&nbsp; 🇬🇧 Ofcom\n\n"
        "🇪🇺 EEAS &nbsp;·&nbsp; 🇪🇺 EC Commission"
    )

pg.run()
