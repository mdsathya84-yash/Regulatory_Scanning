import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
from register.obligation_register import ObligationRegister

st.title("📋 Compliance Obligation Register")
st.caption("Regulations from European Commission, Ofcom and EEAS — mapped to business unit, risk level, and jurisdiction.")

# ── pick up deep-link filters from Home page ─────────────────────────────────
_date_from    = st.session_state.pop("register_date_from",  None)
_risk_preset  = st.session_state.pop("register_risk_filter", None)
_banner_msg   = st.session_state.pop("register_banner",     None)

if _banner_msg:
    col_banner, col_clear = st.columns([5, 1])
    col_banner.info(f"🕐 {_banner_msg}")
    if col_clear.button("✕ Clear filter", key="clear_recent"):
        _date_from = None
        st.rerun()

# ── filters ──────────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    jurisdiction = st.selectbox("Jurisdiction", ["All", "EU", "UK"])
with col2:
    _risk_opts  = ["All", "HIGH", "MEDIUM", "LOW"]
    _risk_idx   = _risk_opts.index(_risk_preset) if _risk_preset in _risk_opts else 0
    risk_filter = st.selectbox("Risk Level", _risk_opts, index=_risk_idx)
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

# ── pull data (date_from injected from Home if navigated via the metric) ──────
obligations = register.search(
    jurisdiction=None if jurisdiction == "All" else jurisdiction,
    status=None,
    keyword=keyword or None,
    date_from=_date_from,
)

if risk_filter != "All":
    obligations = [o for o in obligations if o.get("risk_level") == risk_filter]
if reg_type != "All":
    obligations = [
        o for o in obligations
        if (o.get("regulation_type") or o.get("document_type", "")) == reg_type
    ]
if bu_filter != "All":
    obligations = [o for o in obligations if bu_filter in (o.get("business_unit") or "")]

# ── stats bar ─────────────────────────────────────────────────────────────────
stats = register.stats()
high_risk = sum(1 for o in obligations if o.get("risk_level") == "HIGH")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total in Register", stats["total"])
c2.metric("Showing", len(obligations))
c3.metric("High Risk", high_risk)
c4.metric("EU", stats["by_jurisdiction"].get("EU", 0))
c5.metric("UK", stats["by_jurisdiction"].get("UK", 0))

st.divider()

# ── main table (vertical + horizontal scroll) ─────────────────────────────────
if obligations:
    df = pd.DataFrame(obligations)

    def _fmt_risks(val):
        try:
            risks = json.loads(val) if isinstance(val, str) else (val or [])
            return " | ".join(risks)
        except Exception:
            return str(val or "")

    df["risks"]      = df["associated_risks"].apply(_fmt_risks)
    RISK_COLOURS     = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
    df["risk"]       = df["risk_level"].apply(lambda v: f"{RISK_COLOURS.get(v,'')} {v}")
    df["source_url"] = df["source_url"].fillna("").astype(str)

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
    cols_present = [c for c in display_cols if c in df.columns]
    display_df   = df[cols_present].rename(columns=display_cols)

    def _style_risk(val):
        if "HIGH"   in str(val): return "background-color:#ffe0e0;font-weight:bold"
        if "MEDIUM" in str(val): return "background-color:#fff8e0"
        if "LOW"    in str(val): return "background-color:#e8f5e9"
        return ""

    risk_subset = ["Risk Level"] if "Risk Level" in display_df.columns else []
    styled = display_df.style.applymap(_style_risk, subset=risk_subset)

    # Explicit column widths — total intentionally exceeds viewport to force H-scroll
    col_config = {
        "Regulation Title":       st.column_config.TextColumn(width="large"),
        "Type":                   st.column_config.TextColumn(width="medium"),
        "Date Issued":            st.column_config.TextColumn(width="small"),
        "Jurisdiction":           st.column_config.TextColumn(width="small"),
        "Impacted Business Unit": st.column_config.TextColumn(width="large"),
        "Risk Level":             st.column_config.TextColumn(width="small"),
        "Associated Risks":       st.column_config.TextColumn(width="large"),
        "Source":                 st.column_config.TextColumn(width="small"),
    }
    if "URL" in display_df.columns:
        col_config["URL"] = st.column_config.LinkColumn(
            "URL",
            display_text="Open ↗",
            help="Click to open the source regulation page",
            width="small",
        )

    # height drives vertical scroll; column widths + use_container_width=False
    # keeps the native horizontal scrollbar visible
    _selection = st.dataframe(
        styled,
        use_container_width=False,
        width=1400,
        hide_index=True,
        height=480,
        column_config=col_config,
        on_select="rerun",
        selection_mode="single-row",
    )

    export_cols = [
        "title", "regulation_type", "effective_date", "jurisdiction",
        "business_unit", "risk_level", "risks", "source_name", "source_url",
    ]
    export_df  = df[[c for c in export_cols if c in df.columns]]
    csv_bytes  = export_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export to CSV", data=csv_bytes,
        file_name="compliance_register.csv", mime="text/csv",
    )

    st.divider()

    # ── obligation detail (auto-driven by row click) ──────────────────────────
    st.subheader("Obligation Detail")

    _selected_rows = _selection.selection.rows if _selection and _selection.selection else []
    if not _selected_rows:
        st.caption("Click any row in the table above to view its full details.")
    else:
        ob = obligations[_selected_rows[0]] if _selected_rows[0] < len(obligations) else None
        if ob:
            risks_parsed = []
            try:
                risks_parsed = json.loads(ob.get("associated_risks", "[]"))
            except Exception:
                pass

            risk_level  = ob.get("risk_level", "LOW")
            risk_colour = {"HIGH": "#ffe0e0", "MEDIUM": "#fff8e0", "LOW": "#e8f5e9"}.get(risk_level, "#f5f5f5")
            risk_border = {"HIGH": "#e57373",  "MEDIUM": "#ffb74d", "LOW":  "#81c784"}.get(risk_level, "#ccc")
            risk_badge  = {"HIGH": "#c62828",  "MEDIUM": "#e65100", "LOW":  "#2e7d32"}.get(risk_level, "#555")

            src_url  = ob.get("source_url", "#") or "#"
            src_name = ob.get("source_name", "Source") or "Source"

            risks_html = "".join(
                f"<li style='margin:3px 0'>{r}</li>" for r in risks_parsed
            ) if risks_parsed else "<li>General Regulatory Risk</li>"

            desc = (ob.get("description") or "").replace("<", "&lt;").replace(">", "&gt;")
            desc_block = (
                f"<div style='margin-top:10px'>"
                f"<strong>Description</strong>"
                f"<p style='margin:6px 0 0;font-size:0.85em;color:#333;white-space:pre-wrap'>{desc}</p>"
                f"</div>"
            ) if desc else ""

            html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          font-size: 14px; background: transparent; }}
  .scroll-box {{
    width: 100%;
    height: 380px;
    overflow-x: auto;
    overflow-y: auto;
    border: 1px solid {risk_border};
    border-radius: 8px;
    background: {risk_colour};
    padding: 16px;
  }}
  /* custom scrollbar */
  .scroll-box::-webkit-scrollbar        {{ width: 8px; height: 8px; }}
  .scroll-box::-webkit-scrollbar-track  {{ background: #f0f0f0; border-radius: 4px; }}
  .scroll-box::-webkit-scrollbar-thumb  {{ background: {risk_border}; border-radius: 4px; }}
  .scroll-box::-webkit-scrollbar-corner {{ background: #f0f0f0; }}
  .header {{ font-size: 1.05em; font-weight: 700; color: #1a1a1a; margin-bottom: 8px; }}
  .badge  {{ display:inline-block; font-size:0.75em; font-weight:600; color:#fff;
             background:{risk_badge}; border-radius:4px; padding:2px 8px; margin-left:8px; vertical-align:middle; }}
  .meta   {{ font-size: 0.8em; color: #555; margin-bottom: 14px; }}
  .grid   {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; min-width: 700px; }}
  .card   {{ background: rgba(255,255,255,0.7); border-radius: 6px; padding: 10px 14px; }}
  .card-label {{ font-size: 0.72em; text-transform: uppercase; letter-spacing: 0.05em;
                 color: #777; margin-bottom: 3px; }}
  .card-value {{ font-size: 0.9em; font-weight: 500; color: #1a1a1a; word-break: break-word; }}
  .card-value a {{ color: #1565c0; text-decoration: none; }}
  .card-value a:hover {{ text-decoration: underline; }}
  .risks-block {{ margin-top: 14px; min-width: 700px; }}
  .risks-block strong {{ font-size: 0.85em; text-transform: uppercase;
                         letter-spacing: 0.05em; color: #555; }}
  .risks-block ul {{ margin: 6px 0 0 18px; }}
  .risks-block li {{ font-size: 0.88em; color: #1a1a1a; margin: 4px 0; }}
  .desc-block {{ margin-top: 14px; min-width: 700px; background: rgba(255,255,255,0.6);
                 border-radius: 6px; padding: 10px 14px; }}
  .desc-block strong {{ font-size: 0.85em; text-transform: uppercase;
                        letter-spacing: 0.05em; color: #555; }}
  .desc-block p {{ font-size: 0.85em; color: #333; margin-top: 6px;
                   white-space: pre-wrap; line-height: 1.5; }}
</style>
</head>
<body>
<div class="scroll-box">
  <div class="header">
    {ob.get("title","").replace("<","&lt;").replace(">","&gt;")}
    <span class="badge">{risk_level} RISK</span>
  </div>
  <div class="meta">
    {ob.get("regulation_type","") or ob.get("document_type","")} &nbsp;·&nbsp;
    {ob.get("jurisdiction","")} &nbsp;·&nbsp;
    {ob.get("source_name","")}
  </div>

  <div class="grid">
    <div class="card">
      <div class="card-label">Date Issued</div>
      <div class="card-value">{ob.get("effective_date","—") or "—"}</div>
    </div>
    <div class="card">
      <div class="card-label">Jurisdiction</div>
      <div class="card-value">{ob.get("jurisdiction","—")}</div>
    </div>
    <div class="card">
      <div class="card-label">Source</div>
      <div class="card-value"><a href="{src_url}" target="_blank">{src_name} ↗</a></div>
    </div>
    <div class="card">
      <div class="card-label">Impacted Business Unit</div>
      <div class="card-value">{ob.get("business_unit","—") or "—"}</div>
    </div>
    <div class="card">
      <div class="card-label">Responsible Owner</div>
      <div class="card-value">{ob.get("responsible_owner","—") or "—"}</div>
    </div>
    <div class="card">
      <div class="card-label">Status</div>
      <div class="card-value">{ob.get("status","ACTIVE")}</div>
    </div>
  </div>

  <div class="risks-block">
    <strong>Associated Risks</strong>
    <ul>{risks_html}</ul>
  </div>

  {"<div class='desc-block'><strong>Description / Content</strong><p>" + desc + "</p></div>" if desc else ""}
</div>
</body>
</html>
"""
            components.html(html, height=400, scrolling=True)

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
