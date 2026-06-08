import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import streamlit as st

st.markdown(
    """
    <style>
    .metric-card {
        background: #f8f9fb;
        border: 1px solid #e0e4ea;
        border-radius: 8px;
        padding: 14px 16px 10px;
        text-align: left;
        height: 90px;
    }
    .metric-card .label {
        font-size: 0.78em;
        color: #666;
        font-weight: 500;
        margin-bottom: 4px;
    }
    .metric-card .value {
        font-size: 1.9em;
        font-weight: 700;
        color: #1a1a2e;
        line-height: 1.1;
    }
    .clickable-card {
        background: #eef4ff;
        border: 1px solid #aac4f5;
        border-radius: 8px;
        padding: 10px 16px 4px;
        text-align: left;
        height: 90px;
        cursor: pointer;
        transition: background 0.15s;
    }
    .clickable-card:hover { background: #dce8ff; }
    .clickable-card .label {
        font-size: 0.78em;
        color: #1565c0;
        font-weight: 600;
        margin-bottom: 2px;
    }
    .clickable-card .value {
        font-size: 1.9em;
        font-weight: 700;
        color: #1565c0;
        line-height: 1.1;
    }
    .clickable-card .hint {
        font-size: 0.7em;
        color: #1976d2;
        margin-top: 2px;
    }
    /* shrink the button so it fits inside the card area */
    div[data-testid="stButton"] > button {
        padding: 0 !important;
        background: transparent !important;
        border: none !important;
        color: #1565c0 !important;
        font-size: 0.72em !important;
        font-weight: 600 !important;
        text-decoration: underline !important;
        min-height: 0 !important;
        height: auto !important;
    }
    .source-card {
        background: #f8f9fb;
        border: 1px solid #e0e4ea;
        border-left: 4px solid #1565c0;
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 10px;
    }
    .source-card h4 { margin: 0 0 4px; font-size: 1em; color: #1a1a2e; }
    .source-card p  { margin: 0; font-size: 0.82em; color: #555; }
    .badge {
        display: inline-block;
        font-size: 0.72em;
        font-weight: 600;
        border-radius: 4px;
        padding: 2px 8px;
        margin-right: 4px;
        color: #fff;
    }
    .badge-eu  { background: #003399; }
    .badge-uk  { background: #c8102e; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("⚖️ RegScan — Regulatory Intelligence")
st.markdown("*AI-powered monitoring across UK and EU regulatory sources*")
st.divider()

# ── live stats ────────────────────────────────────────────────────────────────
try:
    from ingestion.vector_store import RegulatoryVectorStore
    from register.obligation_register import ObligationRegister

    vs    = RegulatoryVectorStore()
    reg   = ObligationRegister()
    stats = reg.stats()
    recent = vs.list_recent(days=180)

    from datetime import datetime, timedelta
    cutoff     = (datetime.utcnow() - timedelta(days=180)).strftime("%Y-%m-%d")
    new_obs    = reg.search(date_from=cutoff, status=None)
    new_count  = len(new_obs)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📄 Indexed Chunks",  f"{vs.count():,}")
    c2.metric("📋 Obligations",     f"{stats['total']:,}")
    c3.metric("🔴 High Risk Items", stats.get('by_risk', {}).get('HIGH', 0))
    c5.metric("🌍 Jurisdictions",   len(stats.get('by_jurisdiction', {})))

    # Clickable "New (6 months)" card in c4
    with c4:
        st.markdown(
            f"""<div class="clickable-card">
              <div class="label">🕐 New Obligations (6 months)</div>
              <div class="value">{new_count}</div>
              <div class="hint">Click below to view →</div>
            </div>""",
            unsafe_allow_html=True,
        )
        if st.button("View new obligations", key="btn_new_obs"):
            st.session_state["register_date_from"] = cutoff
            st.session_state["register_banner"]    = f"Showing {new_count} new obligations published since {cutoff}"
            st.switch_page("ui/pages/02_register.py")
except Exception as _e:
    st.warning(f"Could not load data: {_e}")

st.divider()

# ── two-column layout ─────────────────────────────────────────────────────────
left, right = st.columns([3, 2], gap="large")

with left:
    st.markdown("### 🔍 What you can do")

    st.markdown(
        """
        | Page | What it does |
        |------|-------------|
        | 💬 **Chatbot** | Ask natural-language questions about regulations, sanctions, and compliance obligations across all indexed sources |
        | 📋 **Register** | Browse, filter, and export the live Compliance Obligation Register — 678 obligations mapped to business unit, risk level, and source URL |
        """
    )

    st.markdown("### 🗂️ Data Sources")

    sources = [
        ("🇬🇧", "NCSC", "UK", "Cyber guidance, advisories, and threat intelligence"),
        ("🇬🇧", "Ofcom", "UK", "Telecoms, broadcasting, and online safety regulations + 2026 statistical calendar"),
        ("🇪🇺", "EEAS", "EU", "Sanctions, restrictive measures, and foreign policy instruments"),
        ("🇪🇺", "European Commission", "EU", "Regulations, Directives, Decisions, Policies across all DGs"),
    ]

    for flag, name, jur, desc in sources:
        badge_cls = "badge-eu" if jur == "EU" else "badge-uk"
        st.markdown(
            f"""<div class="source-card">
            <h4>{flag} {name} <span class="badge {badge_cls}">{jur}</span></h4>
            <p>{desc}</p>
            </div>""",
            unsafe_allow_html=True,
        )

with right:
    st.markdown("### 📊 Obligation Breakdown")
    try:
        import pandas as pd
        from register.obligation_register import ObligationRegister
        reg = ObligationRegister()
        stats = reg.stats()

        risk_data = stats.get("by_risk", {})
        if risk_data:
            df_risk = pd.DataFrame(
                {"Risk Level": list(risk_data.keys()), "Count": list(risk_data.values())}
            ).sort_values("Count", ascending=False)
            st.bar_chart(df_risk.set_index("Risk Level"), color="#1565c0")

        st.markdown("**By Jurisdiction**")
        for jur, cnt in stats.get("by_jurisdiction", {}).items():
            flag = "🇬🇧" if jur == "UK" else "🇪🇺"
            pct = int(cnt / max(stats["total"], 1) * 100)
            st.markdown(f"{flag} **{jur}** — {cnt:,} &nbsp; `{pct}%`")

        st.divider()
        st.markdown("**Top Regulation Types**")
        for rtype, cnt in list(stats.get("by_type", {}).items())[:6]:
            st.markdown(f"- {rtype}: **{cnt}**")
    except Exception:
        st.info("No data yet.")

st.divider()
st.caption("RegScan · Built with Streamlit · Sources: NCSC, Ofcom, EEAS, European Commission")
