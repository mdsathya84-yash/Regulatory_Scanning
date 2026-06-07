import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import streamlit as st
from rag.chain import RegulatoryRAGChain
from ingestion.vector_store import RegulatoryVectorStore, multi_collection_search

st.title("Regulatory Intelligence Chatbot")
st.caption("Ask questions about regulations, sanctions, and compliance obligations.")

# ── collection map ──────────────────────────────────────────────────────────
SOURCES = {
    "All Sources":         ["regulatory_documents", "ec_regulations", "ofcom_links"],
    "NCSC / EEAS / Ofcom": ["regulatory_documents", "ofcom_links"],
    "EC Commission":       ["ec_regulations"],
}

with st.sidebar:
    st.subheader("Filters")
    data_source = st.selectbox("Data Source", list(SOURCES.keys()), index=0)
    jurisdiction = st.selectbox(
        "Jurisdiction", ["All", "UK", "EU", "APAC", "US", "GLOBAL"], index=0
    )
    doc_type = st.selectbox(
        "Document Type",
        ["All", "REGULATION", "DIRECTIVE", "DECISION", "RECOMMENDATION",
         "SANCTION", "GUIDANCE", "CONSULTATION", "AMENDMENT"],
        index=0,
    )
    n_results = st.slider("Context chunks", min_value=3, max_value=15, value=8)
    st.divider()

    # Collection stats
    try:
        persist_dir = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
        stats = []
        for cname in ["regulatory_documents", "ec_regulations", "ofcom_links"]:
            try:
                vs = RegulatoryVectorStore(persist_dir=persist_dir, collection_name=cname)
                stats.append(f"**{cname}**: {vs.count():,} chunks")
            except Exception:
                stats.append(f"**{cname}**: not loaded")
        st.caption("\n\n".join(stats))
    except Exception:
        pass

    st.divider()
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.rerun()

st.info(
    "Try: *'List new EU regulations published in 2025'* · "
    "*'What directives cover AI and digital markets?'* · "
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
                collections = SOURCES[data_source]
                persist_dir = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")

                chunks = multi_collection_search(
                    query=prompt,
                    collections=collections,
                    n_results=n_results,
                    persist_dir=persist_dir,
                    jurisdiction_filter=None if jurisdiction == "All" else jurisdiction,
                )

                if not chunks:
                    result = {
                        "answer": "No relevant regulatory information found for your query.",
                        "sources": [],
                        "chunks_used": 0,
                    }
                else:
                    # Build context and call LLM via the chain
                    vs = RegulatoryVectorStore(persist_dir=persist_dir)
                    chain = RegulatoryRAGChain(vs)

                    from langchain.schema import SystemMessage, HumanMessage
                    from rag.prompts import SYSTEM_PROMPT, QUERY_PROMPT_TEMPLATE

                    context_parts = []
                    sources = []
                    for chunk in chunks:
                        m = chunk["metadata"]
                        reg_type = m.get("regulation_type", m.get("document_type", ""))
                        date_val = m.get("publication_date", m.get("date_published", "N/A"))
                        context_parts.append(
                            f"[{m.get('source_name', m.get('regulator','EC'))} | "
                            f"{m.get('jurisdiction','EU')} | {date_val}]\n"
                            f"Title: {m.get('title','')}\n"
                            f"Type: {reg_type}\n"
                            f"{chunk['text']}\n"
                            f"URL: {m.get('source_url', m.get('url',''))}\n"
                        )
                        url = m.get("source_url", m.get("url", ""))
                        doc_id = m.get("doc_id", url)
                        if doc_id not in [s.get("doc_id") for s in sources]:
                            sources.append({
                                "doc_id": doc_id,
                                "title": m.get("title", ""),
                                "source": m.get("source_name", m.get("regulator", "EC Commission")),
                                "jurisdiction": m.get("jurisdiction", "EU"),
                                "date": date_val,
                                "url": url,
                                "regulation_type": reg_type,
                                "relevance": chunk["relevance_score"],
                            })

                    context = "\n---\n".join(context_parts)
                    query_prompt = QUERY_PROMPT_TEMPLATE.format(
                        context=context, question=prompt
                    )
                    messages = [
                        SystemMessage(content=SYSTEM_PROMPT),
                        HumanMessage(content=query_prompt),
                    ]
                    response = chain.llm.invoke(messages)
                    result = {
                        "answer": response.content,
                        "sources": sources,
                        "chunks_used": len(chunks),
                    }

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
                    reg_badge = f" `{src['regulation_type']}`" if src.get("regulation_type") else ""
                    st.markdown(
                        f"**{src['title']}**{reg_badge} — {src['source']} | "
                        f"{src['jurisdiction']} | {src.get('date', 'N/A')}  \n"
                        f"[{src['url']}]({src['url']}) | Relevance: {src['relevance']}"
                    )

        st.caption(
            f"Context: {result['chunks_used']} chunks · Source: {data_source}"
        )
        st.session_state.messages.append({"role": "assistant", "content": result["answer"]})
