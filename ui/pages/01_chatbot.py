import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import streamlit as st
from rag.chain import RegulatoryRAGChain
from ingestion.vector_store import RegulatoryVectorStore

st.title("Regulatory Intelligence Chatbot")
st.caption("Ask questions about regulations, sanctions, and compliance obligations.")

with st.sidebar:
    st.subheader("Filters")
    jurisdiction = st.selectbox(
        "Jurisdiction", ["All", "UK", "EU", "APAC", "US", "GLOBAL"], index=0
    )
    doc_type = st.selectbox(
        "Document Type",
        ["All", "REGULATION", "DIRECTIVE", "SANCTION", "GUIDANCE", "CONSULTATION", "AMENDMENT"],
        index=0,
    )
    n_results = st.slider("Context chunks", min_value=3, max_value=15, value=8)
    st.divider()
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.rerun()

st.info(
    "Try: *'List regulations published in the past 6 months'* · "
    "*'What sanctions affect multiple jurisdictions?'* · "
    "*'What cybersecurity obligations apply to telecom operators?'*"
)

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask a regulatory question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Searching regulatory database..."):
            try:
                vs = RegulatoryVectorStore()
                chain = RegulatoryRAGChain(vs)
                result = chain.query(
                    question=prompt,
                    jurisdiction_filter=None if jurisdiction == "All" else jurisdiction,
                    doc_type_filter=None if doc_type == "All" else doc_type,
                    n_results=n_results,
                )
            except Exception as e:
                result = {
                    "answer": f"Error querying the system: {e}",
                    "sources": [],
                    "chunks_used": 0,
                }

        st.markdown(result["answer"])

        if result["sources"]:
            with st.expander(f"Sources ({len(result['sources'])} documents used)"):
                for src in result["sources"]:
                    st.markdown(
                        f"**{src['title']}** — {src['source']} | {src['jurisdiction']} | "
                        f"{src.get('date', 'N/A')}  \n"
                        f"[{src['url']}]({src['url']}) | Relevance: {src['relevance']}"
                    )

        st.caption(f"Context: {result['chunks_used']} chunks retrieved")
        st.session_state.messages.append({"role": "assistant", "content": result["answer"]})
