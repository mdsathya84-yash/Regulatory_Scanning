import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import streamlit as st
from rag.chain import RegulatoryRAGChain
from ingestion.vector_store import RegulatoryVectorStore, multi_collection_search

st.markdown(
    """
    <style>
    .sample-pill button {
        background: #f0f4ff !important;
        border: 1px solid #c5cfe8 !important;
        border-radius: 20px !important;
        font-size: 0.78em !important;
        padding: 4px 12px !important;
        color: #1565c0 !important;
        white-space: nowrap;
    }
    .sample-pill button:hover {
        background: #dce6ff !important;
        border-color: #1565c0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("💬 Regulatory Intelligence Chatbot")
st.caption("Ask anything about EU and UK regulations, sanctions, directives, and compliance obligations.")

# ── collection map ────────────────────────────────────────────────────────────
SOURCES = {
    "🔍 All Sources":           ["regulatory_documents", "ec_regulations", "ofcom_links"],
    "🇬🇧 EEAS / Ofcom":          ["regulatory_documents", "ofcom_links"],
    "🇪🇺 EC Commission":         ["ec_regulations"],
}

# ── sample questions by topic ─────────────────────────────────────────────────
SAMPLE_QUESTIONS = {
    "🤖 AI & Digital": [
        "What EU regulations govern artificial intelligence?",
        "What does the EU AI Act require from high-risk AI systems?",
        "Which directives cover digital markets and platform regulation?",
        "What are the data protection obligations under EU GDPR?",
    ],
    "🔒 Cybersecurity": [
        "What cybersecurity obligations apply to telecom operators?",
        "What does NIS2 require from critical infrastructure operators?",
        "What cybersecurity frameworks apply to UK critical infrastructure?",
        "How does the EU Cyber Resilience Act affect product manufacturers?",
    ],
    "⚠️ Sanctions": [
        "List all active EU sanctions regimes and who they target",
        "What sanctions apply to Russia under EU and UK law?",
        "What are the asset freeze obligations under current EU sanctions?",
        "Which sanctions overlap between UK and EU jurisdictions?",
    ],
    "📡 Telecoms & Media": [
        "What Ofcom regulations apply to broadband providers?",
        "What are the latest Ofcom statistical releases for 2026?",
        "What online safety obligations apply under UK law?",
        "What spectrum and licensing rules does Ofcom enforce?",
    ],
    "📅 Recent Regulations": [
        "List new EU regulations and directives published in 2025",
        "What regulations has the European Commission issued in the last 6 months?",
        "What are the most recent Ofcom compliance publications?",
        "List all new EU decisions and recommendations from 2024–2025",
    ],
    "💼 Business & Finance": [
        "What financial regulations affect banks operating in the EU?",
        "What are the DORA requirements for financial institutions?",
        "What competition law obligations apply under EU antitrust rules?",
        "What environmental compliance rules apply to EU businesses?",
    ],
}

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Search Settings")
    data_source = st.selectbox("📂 Data Source", list(SOURCES.keys()), index=0)
    jurisdiction = st.selectbox(
        "🌍 Jurisdiction", ["All", "UK", "EU"], index=0
    )
    doc_type = st.selectbox(
        "📄 Document Type",
        ["All", "Regulation", "Directive", "Decision", "Recommendation",
         "Sanction", "Guidance", "Consultation", "Amendment"],
        index=0,
    )
    n_results = st.slider("🔢 Context chunks", min_value=3, max_value=15, value=8)
    st.divider()

    try:
        persist_dir = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
        st.markdown("**📊 Index Stats**")
        for cname, label in [
            ("regulatory_documents", "🇬🇧 EEAS/Ofcom"),
            ("ec_regulations",       "🇪🇺 EC Commission"),
            ("ofcom_links",          "📡 Ofcom Links"),
        ]:
            try:
                vs = RegulatoryVectorStore(persist_dir=persist_dir, collection_name=cname)
                st.caption(f"{label}: **{vs.count():,}** chunks")
            except Exception:
                st.caption(f"{label}: not loaded")
    except Exception:
        pass

    st.divider()
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pop("pending_prompt", None)
        st.rerun()

# ── sample question buttons ───────────────────────────────────────────────────
if not st.session_state.get("messages"):
    st.markdown("#### 💡 Try asking...")
    for topic, questions in SAMPLE_QUESTIONS.items():
        st.markdown(f"**{topic}**")
        cols = st.columns(2)
        for i, q in enumerate(questions):
            with cols[i % 2]:
                if st.button(q, key=f"sq_{topic}_{i}", use_container_width=True):
                    st.session_state["pending_prompt"] = q
                    st.rerun()
    st.divider()

# ── conversation ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Pick up a clicked sample question or typed input
pending = st.session_state.pop("pending_prompt", None)
prompt  = st.chat_input("Ask a regulatory question...") or pending

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("🔍 Searching regulatory database..."):
            try:
                collections  = SOURCES[data_source]
                persist_dir  = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
                jur_filter   = None if jurisdiction == "All" else jurisdiction

                chunks = multi_collection_search(
                    query=prompt,
                    collections=collections,
                    n_results=n_results,
                    persist_dir=persist_dir,
                    jurisdiction_filter=jur_filter,
                )

                if not chunks:
                    result = {
                        "answer": "No relevant regulatory information found for your query. Try broadening your search or switching the Data Source filter.",
                        "sources": [],
                        "chunks_used": 0,
                    }
                else:
                    vs    = RegulatoryVectorStore(persist_dir=persist_dir)
                    chain = RegulatoryRAGChain(vs)

                    from langchain.schema import SystemMessage, HumanMessage
                    from rag.prompts import SYSTEM_PROMPT, QUERY_PROMPT_TEMPLATE

                    context_parts = []
                    sources       = []
                    for chunk in chunks:
                        m        = chunk["metadata"]
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
                        url    = m.get("source_url", m.get("url", ""))
                        doc_id = m.get("doc_id", url)
                        if doc_id not in [s.get("doc_id") for s in sources]:
                            sources.append({
                                "doc_id":          doc_id,
                                "title":           m.get("title", ""),
                                "source":          m.get("source_name", m.get("regulator", "EC Commission")),
                                "jurisdiction":    m.get("jurisdiction", "EU"),
                                "date":            date_val,
                                "url":             url,
                                "regulation_type": reg_type,
                                "relevance":       chunk["relevance_score"],
                            })

                    context      = "\n---\n".join(context_parts)
                    query_prompt = QUERY_PROMPT_TEMPLATE.format(context=context, question=prompt)
                    messages     = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=query_prompt)]
                    response     = chain.llm.invoke(messages)
                    result       = {"answer": response.content, "sources": sources, "chunks_used": len(chunks)}

            except Exception as e:
                result = {"answer": f"⚠️ Error querying the system: {e}", "sources": [], "chunks_used": 0}

        st.markdown(result["answer"])

        if result["sources"]:
            with st.expander(f"📚 Sources — {len(result['sources'])} documents referenced", expanded=False):
                for src in result["sources"]:
                    jur_flag = "🇬🇧" if src.get("jurisdiction") == "UK" else "🇪🇺"
                    rtype    = src.get("regulation_type", "")
                    badge    = f" `{rtype}`" if rtype else ""
                    st.markdown(
                        f"{jur_flag} **{src['title']}**{badge}  \n"
                        f"📌 {src['source']} · {src['jurisdiction']} · 📅 {src.get('date','N/A')}  \n"
                        f"🔗 [{src['url']}]({src['url']}) · Relevance: `{src['relevance']}`"
                    )
                    st.markdown("---")

        st.caption(f"🔢 {result['chunks_used']} chunks retrieved · 📂 {data_source}")
        st.session_state.messages.append({"role": "assistant", "content": result["answer"]})
