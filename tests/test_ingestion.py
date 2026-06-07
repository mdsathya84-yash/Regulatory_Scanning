"""
Tests for chunking, deduplication, and vector store ingestion logic.
ChromaDB/OpenAI tests are skipped unless OPENAI_API_KEY is set.
"""

import os
import pytest
from datetime import datetime
from scraper.models import RegulatoryDocument, Jurisdiction, DocumentType
from ingestion.chunker import RegulatoryChunker
from ingestion.deduplicator import ChunkDeduplicator


def _make_doc(content: str = None, doc_id: str = "test001") -> RegulatoryDocument:
    return RegulatoryDocument(
        id=doc_id,
        title="Test Regulation",
        content=content or ("This is a test regulatory document. " * 50),
        source_url="https://www.ncsc.gov.uk/guidance/test",
        source_name="NCSC",
        jurisdiction=Jurisdiction.UK,
        document_type=DocumentType.GUIDANCE,
        last_scraped=datetime.utcnow(),
        content_hash="abc123",
        tags=["cybersecurity", "encryption"],
        affected_jurisdictions=[Jurisdiction.UK, Jurisdiction.EU],
    )


# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------

class TestRegulatoryChunker:
    def test_chunks_are_produced(self):
        chunker = RegulatoryChunker()
        doc = _make_doc()
        chunks = chunker.chunk(doc)
        assert len(chunks) > 0

    def test_chunk_ids_are_unique(self):
        chunker = RegulatoryChunker()
        doc = _make_doc()
        chunks = chunker.chunk(doc)
        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_chunk_metadata_fields(self):
        chunker = RegulatoryChunker()
        doc = _make_doc()
        chunks = chunker.chunk(doc)
        required_keys = {
            "doc_id", "title", "source_url", "source_name", "jurisdiction",
            "document_type", "content_hash", "chunk_index", "total_chunks",
        }
        for chunk in chunks:
            assert required_keys.issubset(chunk["metadata"].keys())

    def test_chunk_metadata_values(self):
        chunker = RegulatoryChunker()
        doc = _make_doc()
        chunks = chunker.chunk(doc)
        for i, chunk in enumerate(chunks):
            assert chunk["metadata"]["chunk_index"] == i
            assert chunk["metadata"]["total_chunks"] == len(chunks)
            assert chunk["metadata"]["source_name"] == "NCSC"
            assert chunk["metadata"]["jurisdiction"] == "UK"

    def test_affected_jurisdictions_serialised(self):
        chunker = RegulatoryChunker()
        doc = _make_doc()
        chunks = chunker.chunk(doc)
        for chunk in chunks:
            aff = chunk["metadata"]["affected_jurisdictions"]
            assert "UK" in aff
            assert "EU" in aff

    def test_small_doc_single_chunk(self):
        chunker = RegulatoryChunker(chunk_size=800)
        doc = _make_doc(content="Short document.")
        chunks = chunker.chunk(doc)
        assert len(chunks) == 1
        assert chunks[0]["metadata"]["chunk_index"] == 0

    def test_custom_chunk_size(self):
        chunker = RegulatoryChunker(chunk_size=200, chunk_overlap=20)
        long_content = "word " * 500
        doc = _make_doc(content=long_content)
        chunks = chunker.chunk(doc)
        assert len(chunks) > 2


# ---------------------------------------------------------------------------
# Deduplicator
# ---------------------------------------------------------------------------

class TestChunkDeduplicator:
    def test_first_pass_all_new(self):
        dedup = ChunkDeduplicator()
        chunker = RegulatoryChunker()
        chunks = chunker.chunk(_make_doc())
        new, skipped = dedup.filter_new(chunks)
        assert len(new) == len(chunks)
        assert skipped == 0

    def test_second_pass_all_duplicates(self):
        dedup = ChunkDeduplicator()
        chunker = RegulatoryChunker()
        chunks = chunker.chunk(_make_doc())
        dedup.filter_new(chunks)               # first pass
        new, skipped = dedup.filter_new(chunks) # second pass
        assert len(new) == 0
        assert skipped == len(chunks)

    def test_filter_against_store_skips_unchanged(self):
        dedup = ChunkDeduplicator()
        chunker = RegulatoryChunker()
        doc = _make_doc()
        chunks = chunker.chunk(doc)
        existing_hashes = {doc.content_hash}
        new, skipped = dedup.filter_against_store(chunks, existing_hashes)
        assert skipped == len(chunks)
        assert len(new) == 0

    def test_filter_against_store_passes_new_hash(self):
        dedup = ChunkDeduplicator()
        chunker = RegulatoryChunker()
        chunks = chunker.chunk(_make_doc())
        new, skipped = dedup.filter_against_store(chunks, existing_content_hashes=set())
        assert len(new) == len(chunks)


# ---------------------------------------------------------------------------
# Vector store (skipped without API key)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
def test_vector_store_upsert_and_search(tmp_path):
    from ingestion.vector_store import RegulatoryVectorStore
    vs = RegulatoryVectorStore(persist_dir=str(tmp_path))
    chunker = RegulatoryChunker()
    doc = _make_doc(content="Multi-factor authentication is mandatory for all remote access points.")
    chunks = chunker.chunk(doc)
    count = vs.upsert_chunks(chunks)
    assert count == len(chunks)

    results = vs.semantic_search("MFA requirements for remote access")
    assert len(results) > 0
    assert results[0]["relevance_score"] >= 0.0
