import streamlit as st
from typing import Dict, Any


def regulation_card(doc: Dict[str, Any], show_content: bool = False):
    """
    Renders a styled card for a single regulatory document or obligation.

    Args:
        doc: dict with keys: title, source_name, jurisdiction, document_type,
             publication_date, source_url, tags, content (optional).
        show_content: whether to show a content preview in an expander.
    """
    TYPE_COLORS = {
        "REGULATION": "blue",
        "DIRECTIVE": "violet",
        "SANCTION": "red",
        "GUIDANCE": "green",
        "CONSULTATION": "orange",
        "AMENDMENT": "yellow",
    }

    doc_type = doc.get("document_type", "GUIDANCE")
    color = TYPE_COLORS.get(doc_type, "gray")

    with st.container():
        col_main, col_meta = st.columns([3, 1])

        with col_main:
            st.markdown(f"**{doc.get('title', 'Untitled')}**")
            tags = doc.get("tags", "")
            if tags:
                tag_list = tags.split(",") if isinstance(tags, str) else tags
                st.markdown(" ".join(f"`{t.strip()}`" for t in tag_list if t.strip()))

        with col_meta:
            st.markdown(f":{color}[**{doc_type}**]")
            st.caption(
                f"{doc.get('source_name', '')} | {doc.get('jurisdiction', '')}  \n"
                f"{doc.get('publication_date', '')[:10] if doc.get('publication_date') else 'Date unknown'}"
            )
            url = doc.get("source_url", "")
            if url:
                st.markdown(f"[View source]({url})")

        if show_content and doc.get("content"):
            with st.expander("Content preview"):
                st.text(doc["content"][:500] + "..." if len(doc["content"]) > 500 else doc["content"])

        st.divider()
