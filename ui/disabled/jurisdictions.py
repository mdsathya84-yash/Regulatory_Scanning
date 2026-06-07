import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import streamlit as st
import pandas as pd

st.title("Multi-Jurisdiction Impact Map")
st.caption("Cross-border regulatory coverage and impact analysis.")

JURISDICTION_INFO = {
    "UK": {
        "flag": "🇬🇧",
        "sources": ["NCSC", "Ofcom"],
        "key_frameworks": ["NIS Regulations 2018", "UK GDPR", "Online Safety Act 2023", "PECR"],
        "regulator": "ICO, Ofcom, FCA, NCSC",
        "color": "#003366",
    },
    "EU": {
        "flag": "🇪🇺",
        "sources": ["EEAS"],
        "key_frameworks": ["NIS2 Directive", "GDPR", "EU Sanctions Regime", "CRA", "DORA"],
        "regulator": "ENISA, ECB, ESMA, DG Connect",
        "color": "#003399",
    },
    "US": {
        "flag": "🇺🇸",
        "sources": ["OFAC (planned)"],
        "key_frameworks": ["OFAC Sanctions", "CCPA", "HIPAA", "FISMA", "FCC Rules"],
        "regulator": "OFAC, FCC, FTC, CISA",
        "color": "#B22234",
    },
    "APAC": {
        "flag": "🌏",
        "sources": ["Planned"],
        "key_frameworks": ["PDPA (SG)", "PIPL (CN)", "Privacy Act (AU)", "IT Act (IN)"],
        "regulator": "PDPC, CAC, OAIC, MeitY",
        "color": "#FF6600",
    },
}

# Overview grid
st.subheader("Coverage Overview")
cols = st.columns(len(JURISDICTION_INFO))
for col, (jur, info) in zip(cols, JURISDICTION_INFO.items()):
    with col:
        st.markdown(f"### {info['flag']} {jur}")
        st.markdown(f"**Sources:** {', '.join(info['sources'])}")
        st.markdown(f"**Regulator:** {info['regulator']}")
        with st.expander("Key Frameworks"):
            for fw in info["key_frameworks"]:
                st.markdown(f"- {fw}")

st.divider()

# Cross-jurisdiction impact table
st.subheader("Cross-Jurisdiction Regulation Tracker")

try:
    from ingestion.vector_store import RegulatoryVectorStore
    vs = RegulatoryVectorStore()
    recent = vs.list_recent(days=365)

    if recent:
        rows = []
        for doc in recent:
            affected = doc.get("affected_jurisdictions", "")
            jurisdictions = affected.split(",") if affected else [doc.get("jurisdiction", "")]
            if len(jurisdictions) > 1:
                rows.append({
                    "Title": doc.get("title", "")[:80],
                    "Source": doc.get("source_name", ""),
                    "Primary Jurisdiction": doc.get("jurisdiction", ""),
                    "Also Affects": ", ".join(j for j in jurisdictions if j != doc.get("jurisdiction")),
                    "Published": doc.get("publication_date", "")[:10],
                    "Type": doc.get("document_type", ""),
                })

        if rows:
            st.markdown(f"**{len(rows)} cross-jurisdictional regulations found**")
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No cross-jurisdictional regulations found in the indexed data.")
    else:
        st.info("No data indexed yet. Run the scraper pipeline to populate.")
except Exception as e:
    st.warning(f"Could not load vector store data: {e}")

st.divider()

# Sanction overlap heatmap (static demo)
st.subheader("Sanction Regime Overlap (Conceptual)")
overlap_data = {
    "": ["UK", "EU", "US", "APAC"],
    "UK": [1.0, 0.85, 0.70, 0.30],
    "EU": [0.85, 1.0, 0.65, 0.25],
    "US": [0.70, 0.65, 1.0, 0.45],
    "APAC": [0.30, 0.25, 0.45, 1.0],
}
df_heat = pd.DataFrame(overlap_data).set_index("")
st.markdown("Overlap score (0–1) between sanction regimes — higher means more shared designations.")
st.dataframe(df_heat, use_container_width=True)
