import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import streamlit as st
import pandas as pd
from register.obligation_register import ObligationRegister

st.title("Compliance Obligation Register")
st.caption("Live register of compliance obligations linked to source, BU, owner, jurisdiction, and risk.")

col1, col2, col3, col4 = st.columns(4)
with col1:
    jurisdiction = st.selectbox("Jurisdiction", ["All", "UK", "EU", "APAC", "US", "GLOBAL"])
with col2:
    status_filter = st.selectbox("Status", ["ACTIVE", "UNDER_REVIEW", "SUPERSEDED", "All"])
with col3:
    business_unit = st.text_input("Business Unit", placeholder="e.g. Network, Legal...")
with col4:
    keyword = st.text_input("Keyword search", placeholder="e.g. sanctions, encryption...")

register = ObligationRegister()

obligations = register.search(
    jurisdiction=None if jurisdiction == "All" else jurisdiction,
    business_unit=business_unit or None,
    status=None if status_filter == "All" else status_filter,
    keyword=keyword or None,
)

# Stats bar
stats = register.stats()
c1, c2, c3 = st.columns(3)
c1.metric("Total in Register", stats["total"])
c2.metric("Showing", len(obligations))
c3.metric("Active", stats["by_status"].get("ACTIVE", 0))

st.divider()

if obligations:
    df = pd.DataFrame(obligations)

    # Colour-code status
    def style_status(val):
        colours = {"ACTIVE": "background-color:#d4edda", "UNDER_REVIEW": "#fff3cd", "SUPERSEDED": "#f8d7da"}
        return colours.get(val, "")

    display_cols = [
        "title", "source_name", "jurisdiction", "business_unit",
        "responsible_owner", "effective_date", "status", "tags",
    ]
    available = [c for c in display_cols if c in df.columns]

    styled = df[available].style.applymap(style_status, subset=["status"] if "status" in available else [])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Export button
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export to CSV",
        data=csv,
        file_name="compliance_obligations.csv",
        mime="text/csv",
    )

    # Detail expander
    selected_title = st.selectbox("View obligation detail", ["—"] + [o["title"] for o in obligations])
    if selected_title != "—":
        ob = next(o for o in obligations if o["title"] == selected_title)
        with st.expander(f"Detail: {ob['title']}", expanded=True):
            st.json(ob)
else:
    st.info("No obligations found. Run the scraper to populate the register, or adjust your filters.")
