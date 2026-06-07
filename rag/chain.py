import os
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from rag.prompts import SYSTEM_PROMPT, QUERY_PROMPT_TEMPLATE
from ingestion.vector_store import RegulatoryVectorStore
from typing import Dict, Any


class RegulatoryRAGChain:
    """
    LLM failover chain: gpt-4o-mini → gpt-3.5-turbo → groq/llama-3.3-70b
    Retrieves semantically relevant chunks and answers regulatory queries.
    """

    def __init__(self, vector_store: RegulatoryVectorStore):
        self.vector_store = vector_store
        self.llm = self._build_llm()

    def _build_llm(self):
        """Build LLM — Groq primary, OpenAI gateway fallback.
        SSL verification is disabled globally in ui/app.py via httpx patch."""
        from langchain_groq import ChatGroq
        try:
            return ChatGroq(
                model="llama-3.3-70b-versatile",
                groq_api_key=os.environ["GROQ_API_KEY"],
                temperature=0.1,
            )
        except Exception:
            import httpx
            base_url = os.environ.get("OPENAI_BASE_URL")
            return ChatOpenAI(
                model="gpt-4o-mini",
                api_key=os.environ["OPENAI_API_KEY"],
                base_url=base_url,
                http_client=httpx.Client(verify=False, timeout=60.0),
                temperature=0.1,
                streaming=False,
            )

    def query(
        self,
        question: str,
        jurisdiction_filter: str = None,
        doc_type_filter: str = None,
        n_results: int = 8,
    ) -> Dict[str, Any]:
        chunks = self.vector_store.semantic_search(
            query=question,
            n_results=n_results,
            jurisdiction_filter=jurisdiction_filter,
            doc_type_filter=doc_type_filter,
        )

        if not chunks:
            return {
                "answer": "No relevant regulatory information found for your query.",
                "sources": [],
                "chunks_used": 0,
            }

        context_parts = []
        sources = []
        for chunk in chunks:
            m = chunk["metadata"]
            context_parts.append(
                f"[{m['source_name']} | {m['jurisdiction']} | {m.get('publication_date', 'N/A')}]\n"
                f"Title: {m['title']}\n"
                f"{chunk['text']}\n"
                f"URL: {m['source_url']}\n"
            )
            if m["doc_id"] not in [s.get("doc_id") for s in sources]:
                sources.append({
                    "doc_id": m["doc_id"],
                    "title": m["title"],
                    "source": m["source_name"],
                    "jurisdiction": m["jurisdiction"],
                    "date": m.get("publication_date", ""),
                    "url": m["source_url"],
                    "relevance": chunk["relevance_score"],
                })

        context = "\n---\n".join(context_parts)
        prompt = QUERY_PROMPT_TEMPLATE.format(context=context, question=question)

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        response = self.llm.invoke(messages)

        return {
            "answer": response.content,
            "sources": sources,
            "chunks_used": len(chunks),
        }
