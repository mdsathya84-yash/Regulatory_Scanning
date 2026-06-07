import hashlib
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class ChunkDeduplicator:
    """
    Hash-based deduplication for document chunks before ChromaDB ingestion.
    Prevents re-embedding identical content when a scrape revisits unchanged pages.
    """

    def __init__(self):
        self._seen_hashes: set = set()

    def filter_new(
        self, chunks: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Return only chunks whose content hasn't been seen this session.
        Returns (new_chunks, skipped_count).
        """
        new_chunks = []
        skipped = 0
        for chunk in chunks:
            h = self._chunk_hash(chunk["text"])
            if h not in self._seen_hashes:
                self._seen_hashes.add(h)
                new_chunks.append(chunk)
            else:
                skipped += 1
        if skipped:
            logger.debug(f"Deduplicator skipped {skipped} duplicate chunks")
        return new_chunks, skipped

    def filter_against_store(
        self,
        chunks: List[Dict[str, Any]],
        existing_content_hashes: set,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Filter chunks whose parent document content_hash already exists in the store.
        Use this to skip re-embedding entire documents that haven't changed.
        """
        new_chunks = []
        skipped = 0
        for chunk in chunks:
            doc_hash = chunk["metadata"].get("content_hash", "")
            if doc_hash and doc_hash in existing_content_hashes:
                skipped += 1
            else:
                new_chunks.append(chunk)
        if skipped:
            logger.info(f"Skipped {skipped} chunks from unchanged documents")
        return new_chunks, skipped

    @staticmethod
    def _chunk_hash(text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    def get_existing_hashes_from_store(self, vector_store) -> set:
        """Query ChromaDB to get all known content_hash values."""
        try:
            results = vector_store.collection.get(include=["metadatas"])
            return {m.get("content_hash", "") for m in results["metadatas"]}
        except Exception as e:
            logger.warning(f"Could not fetch existing hashes: {e}")
            return set()
