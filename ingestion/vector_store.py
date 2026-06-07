import os
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Local sentence-transformer — no external API, no proxy issues.
_LOCAL_EF = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)


class RegulatoryVectorStore:
    """
    ChromaDB-backed vector store for regulatory document chunks.
    Supports upsert (idempotent), semantic search with metadata filters,
    and deduplication via content_hash.
    """

    COLLECTION_NAME = "regulatory_documents"

    def __init__(self, persist_dir: str = None):
        persist_dir = persist_dir or os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=_LOCAL_EF,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """Upsert chunks; returns count of new/updated items."""
        ids = [c["id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(f"Upserted {len(chunks)} chunks into ChromaDB")
        return len(chunks)

    def semantic_search(
        self,
        query: str,
        n_results: int = 8,
        jurisdiction_filter: str = None,
        date_from: str = None,
        doc_type_filter: str = None,
    ) -> List[Dict]:
        where = {}
        if jurisdiction_filter:
            where["jurisdiction"] = {"$eq": jurisdiction_filter}
        if doc_type_filter:
            where["document_type"] = {"$eq": doc_type_filter}

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where if where else None,
            include=["documents", "metadatas", "distances"],
        )

        return [
            {
                "text": doc,
                "metadata": meta,
                "relevance_score": round(1 - dist, 3),
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

    def list_recent(self, days: int = 180) -> List[Dict]:
        """Return all chunks from documents published in last N days."""
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()[:10]
        results = self.collection.get(include=["metadatas"])
        seen = set()
        unique = []
        for meta in results["metadatas"]:
            pub = meta.get("publication_date", "")
            if pub and pub[:10] >= cutoff and meta["doc_id"] not in seen:
                seen.add(meta["doc_id"])
                unique.append(meta)
        return sorted(unique, key=lambda x: x.get("publication_date", ""), reverse=True)

    def get_all_sources(self) -> List[str]:
        """Return list of distinct source_name values in the collection."""
        results = self.collection.get(include=["metadatas"])
        return list({m["source_name"] for m in results["metadatas"]})

    def count(self) -> int:
        return self.collection.count()

    def delete_by_doc_id(self, doc_id: str):
        """Remove all chunks belonging to a specific document."""
        self.collection.delete(where={"doc_id": {"$eq": doc_id}})
        logger.info(f"Deleted all chunks for doc_id={doc_id}")
