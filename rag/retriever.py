from typing import List, Dict, Any, Optional
from ingestion.vector_store import RegulatoryVectorStore
import logging

logger = logging.getLogger(__name__)


class RegulatoryRetriever:
    """
    Semantic retrieval layer over ChromaDB.
    Supports jurisdiction/doc-type filters, MMR-style diversity, and hybrid re-ranking.
    """

    def __init__(self, vector_store: RegulatoryVectorStore):
        self.vs = vector_store

    def retrieve(
        self,
        query: str,
        n_results: int = 8,
        jurisdiction: Optional[str] = None,
        doc_type: Optional[str] = None,
        min_relevance: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """Retrieve and filter chunks by relevance threshold."""
        raw = self.vs.semantic_search(
            query=query,
            n_results=n_results,
            jurisdiction_filter=jurisdiction,
            doc_type_filter=doc_type,
        )
        filtered = [c for c in raw if c["relevance_score"] >= min_relevance]
        logger.debug(
            f"Retrieved {len(raw)} chunks, {len(filtered)} above threshold {min_relevance}"
        )
        return filtered

    def retrieve_diverse(
        self,
        query: str,
        n_results: int = 8,
        jurisdiction: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve with source diversity — cap results per source_name to avoid
        one document dominating the context window.
        """
        # Fetch more to allow deduplication
        raw = self.vs.semantic_search(query=query, n_results=n_results * 3, jurisdiction_filter=jurisdiction)

        source_counts: Dict[str, int] = {}
        MAX_PER_SOURCE = max(2, n_results // 3)
        diverse = []
        for chunk in raw:
            src = chunk["metadata"].get("source_name", "unknown")
            count = source_counts.get(src, 0)
            if count < MAX_PER_SOURCE:
                diverse.append(chunk)
                source_counts[src] = count + 1
            if len(diverse) >= n_results:
                break

        return diverse

    def retrieve_by_doc_id(self, doc_id: str) -> List[Dict[str, Any]]:
        """Fetch all chunks for a specific document ID (ordered by chunk_index)."""
        results = self.vs.collection.get(
            where={"doc_id": {"$eq": doc_id}},
            include=["documents", "metadatas"],
        )
        chunks = [
            {"text": doc, "metadata": meta}
            for doc, meta in zip(results["documents"], results["metadatas"])
        ]
        return sorted(chunks, key=lambda c: c["metadata"].get("chunk_index", 0))
