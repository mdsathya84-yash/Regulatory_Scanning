import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import streamlit as st
import pandas as pd
import json
from register.obligation_register import ObligationRegister

st.title("Compliance Obligation Register")
st.caption("Regulations from European Commission, Ofcom and EEAS — mapped to business unit, risk level, and jurisdiction.")

# ── filters ──────────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    jurisdiction = st.selectbox("Jurisdiction", ["All", "EU", "UK"])
with col2:
    risk_filter = st.selectbox("Risk Level", ["All", "HIGH", "MEDIUM", "LOW"])
with col3:
    reg_type_opts = [
        "All", "Regulation", "Directive", "Decision", "Recommendation",
        "Law/Legislation", "Policy/Strategy", "News/Press Release",
        "Statistical Release", "Publication",
    ]
    reg_type = st.selectbox("Regulation Type", reg_type_opts)
with col4:
    bu_filter = st.selectbox("Business Unit", [
        "All",
        "Finance / Treasury",
        "Technology / Cybersecurity",
        "Technology / AI Governance",
        "Technology / Digital",
        "Technology / Legal / Compliance",
        "Technology / Network Engineering",
        "Marketing / Broadcasting",
        "Legal / Compliance",
        "Legal / Competition",
        "Legal / Risk / Sanctions",
        "Operations / Supply Chain",
        "Operations / Sustainability",
        "Operations / Product",
        "HR / People",
        "Healthcare / Operations",
    ])
with col5:
    keyword = st.text_input("Keyword search", placeholder="e.g. AI, GDPR, sanctions...")

register = ObligationRegister()

# ── pull data ────────────────────────────────────────────────────────────────
obligations = register.search(
    jurisdiction=None if jurisdiction == "All" else jurisdiction,
    status=None,   # show all statuses
    keyword=keyword or None,
)

# Apply client-side filters not in the search method
if risk_filter != "All":
    obligations = [o for o in obligations if o.get("risk_level") == risk_filter]
if reg_type != "All":
    obligations = [
        o for o in obligations
        if (o.get("regulation_type") or o.get("document_type", "")) == reg_type
    ]
if bu_filter != "All":
    obligations = [o for o in obligations if bu_filter in (o.get("business_unit") or "")]

# ── stats bar ────────────────────────────────────────────────────────────────
stats = register.stats()
high_risk = sum(1 for o in obligations if o.get("risk_level") == "HIGH")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total in Register", stats["total"])
c2.metric("Showing", len(obligations))
c3.metric("High Risk", high_risk, delta=None)
c4.metric("EU", stats["by_jurisdiction"].get("EU", 0))
c5.metric("UK", stats["by_jurisdiction"].get("UK", 0))

st.divider()

# ── main table ───────────────────────────────────────────────────────────────
if obligations:
    df = pd.DataFrame(obligations)

    # Unpack associated_risks JSON → readable string
    def _fmt_risks(val):
        try:
            risks = json.loads(val) if isinstance(val, str) else (val or [])
            return " | ".join(risks)
        except Exception:
            return str(val or "")

    df["risks"] = df["associated_risks"].apply(_fmt_risks)

    # Risk level colour tag
    RISK_COLOURS = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
    df["risk"] = df["risk_level"].apply(lambda v: f"{RISK_COLOURS.get(v, '')} {v}")

    # Clickable URL (markdown)
    df["source_link"] = df.apply(
        lambda r: f"[{r.get('source_name','Link')}]({r.get('source_url','#')})"
        if r.get("source_url") else r.get("source_name", ""), axis=1
    )

    display_cols = {
        "title":           "Regulation Title",
        "regulation_type": "Type",
        "effective_date":  "Date Issued",
        "jurisdiction":    "Jurisdiction",
        "business_unit":   "Impacted Business Unit",
        "risk":            "Risk Level",
        "risks":           "Associated Risks",
        "source_name":     "Source",
        "source_url":      "URL",
    }

    # Only use columns that exist
    cols_present = [c for c in display_cols if c in df.columns]
    display_df = df[cols_present].rename(columns=display_cols)

    # Ensure URL column has clean string values
    if "URL" in display_df.columns:
        display_df["URL"] = display_df["URL"].fillna("").astype(str)

    # Style risk level cells
    def _style_risk(val):
        if "HIGH" in str(val):
            return "background-color:#ffe0e0;font-weight:bold"
        if "MEDIUM" in str(val):
            return "background-color:#fff8e0"
        if "LOW" in str(val):
            return "background-color:#e8f5e9"
        return ""

    risk_subset = ["Risk Level"] if "Risk Level" in display_df.columns else []
    styled = display_df.style.applymap(_style_risk, subset=risk_subset)

    col_config = {}
    if "URL" in display_df.columns:
        col_config["URL"] = st.column_config.LinkColumn(
            "URL",
            display_text="Open ↗",
            help="Click to open the source regulation page",
        )

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=500,
        column_config=col_config,
    )

    # Export
    export_cols = [
        "title", "regulation_type", "effective_date", "jurisdiction",
        "business_unit", "risk_level", "risks", "source_name", "source_url",
    ]
    export_df = df[[c for c in export_cols if c in df.columns]]
    csv_bytes = export_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export to CSV",
        data=csv_bytes,
        file_name="compliance_register.csv",
        mime="text/csv",
    )

    st.divider()

    # ── detail panel ─────────────────────────────────────────────────────────
    st.subheader("Obligation Detail")
    titles = [o["title"] for o in obligations]
    selected = st.selectbox("Select a regulation to inspect", ["—"] + titles)

    if selected != "—":
        ob = next((o for o in obligations if o["title"] == selected), None)
        if ob:
            risks_parsed = []
            try:
                risks_parsed = json.loads(ob.get("associated_risks", "[]"))
            except Exception:
                pass

            risk_colour = {"HIGH": "#ffe0e0", "MEDIUM": "#fff8e0", "LOW": "#e8f5e9"}.get(
                ob.get("risk_level", "LOW"), "#f5f5f5"
            )

            st.markdown(
                f"<div style='background:{risk_colour};padding:12px;border-radius:8px;margin-bottom:8px'>"
                f"<strong>{ob['title']}</strong> &nbsp;"
                f"<span style='font-size:0.8em;color:#555'>{ob.get('regulation_type','')} · "
                f"{ob.get('jurisdiction','')} · {ob.get('risk_level','')} risk</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            d1, d2, d3 = st.columns(3)
            d1.markdown(f"**Date Issued**  \n{ob.get('effective_date','—') or '—'}")
            d2.markdown(f"**Jurisdiction**  \n{ob.get('jurisdiction','')}")
            d3.markdown(f"**Source**  \n[{ob.get('source_name','')}]({ob.get('source_url','#')})")

            d4, d5 = st.columns(2)
            d4.markdown(f"**Impacted Business Unit**  \n{ob.get('business_unit','—') or '—'}")
            d5.markdown(f"**Responsible Owner**  \n{ob.get('responsible_owner','—') or '—'}")

            if risks_parsed:
                st.markdown("**Associated Risks**")
                for r in risks_parsed:
                    st.markdown(f"- {r}")

            if ob.get("description"):
                with st.expander("Description / Content"):
                    st.write(ob["description"])
else:
    st.info("No obligations match the current filters.")

# ── risk summary chart ────────────────────────────────────────────────────────
with st.expander("Risk Distribution", expanded=False):
    if obligations:
        risk_counts = pd.Series([o.get("risk_level", "LOW") for o in obligations]).value_counts()
        st.bar_chart(risk_counts)

    bu_counts = pd.Series(
        [o.get("business_unit", "Unknown") for o in obligations if o.get("business_unit")]
    ).value_counts().head(12)
    if not bu_counts.empty:
        st.markdown("**Obligations by Business Unit**")
        st.bar_chart(bu_counts)
