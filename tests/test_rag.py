"""
Tests for RAG chain, retriever, and prompt templates.
LLM tests are skipped unless OPENAI_API_KEY is set.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from rag.prompts import SYSTEM_PROMPT, QUERY_PROMPT_TEMPLATE


# ---------------------------------------------------------------------------
# Prompt template tests
# ---------------------------------------------------------------------------

class TestPrompts:
    def test_system_prompt_not_empty(self):
        assert len(SYSTEM_PROMPT) > 100
        assert "RegBot" in SYSTEM_PROMPT

    def test_query_prompt_template_renders(self):
        rendered = QUERY_PROMPT_TEMPLATE.format(
            context="[NCSC | UK | 2024-01-01]\nTitle: Test\nContent here",
            question="What are the MFA requirements?",
        )
        assert "MFA requirements" in rendered
        assert "Direct Answer" in rendered
        assert "Compliance Obligations" in rendered

    def test_query_prompt_template_has_required_placeholders(self):
        assert "{context}" in QUERY_PROMPT_TEMPLATE
        assert "{question}" in QUERY_PROMPT_TEMPLATE


# ---------------------------------------------------------------------------
# Retriever tests (mocked vector store)
# ---------------------------------------------------------------------------

class TestRegulatoryRetriever:
    def _make_mock_vs(self, results=None):
        vs = MagicMock()
        vs.semantic_search.return_value = results or [
            {
                "text": "MFA is mandatory for all remote access.",
                "metadata": {
                    "doc_id": "abc1",
                    "title": "NCSC MFA Guidance",
                    "source_name": "NCSC",
                    "jurisdiction": "UK",
                    "document_type": "GUIDANCE",
                    "publication_date": "2024-01-15",
                    "source_url": "https://ncsc.gov.uk/guidance/mfa",
                    "content_hash": "deadbeef",
                    "chunk_index": 0,
                    "total_chunks": 3,
                },
                "relevance_score": 0.87,
            }
        ]
        return vs

    def test_retrieve_returns_chunks(self):
        from rag.retriever import RegulatoryRetriever
        vs = self._make_mock_vs()
        retriever = RegulatoryRetriever(vs)
        chunks = retriever.retrieve("MFA requirements")
        assert len(chunks) > 0

    def test_retrieve_filters_low_relevance(self):
        from rag.retriever import RegulatoryRetriever
        low_relevance = [{"text": "x", "metadata": {}, "relevance_score": 0.1}]
        vs = self._make_mock_vs(low_relevance)
        retriever = RegulatoryRetriever(vs)
        chunks = retriever.retrieve("anything", min_relevance=0.5)
        assert len(chunks) == 0

    def test_retrieve_diverse_caps_per_source(self):
        from rag.retriever import RegulatoryRetriever
        many = [
            {
                "text": f"chunk {i}",
                "metadata": {"source_name": "NCSC", "doc_id": str(i)},
                "relevance_score": 0.9,
            }
            for i in range(20)
        ]
        vs = MagicMock()
        vs.semantic_search.return_value = many
        retriever = RegulatoryRetriever(vs)
        diverse = retriever.retrieve_diverse("query", n_results=6)
        ncsc_count = sum(1 for c in diverse if c["metadata"].get("source_name") == "NCSC")
        assert ncsc_count <= max(2, 6 // 3)


# ---------------------------------------------------------------------------
# RAG chain tests (mocked)
# ---------------------------------------------------------------------------

class TestRegulatoryRAGChain:
    def _make_mock_vs(self):
        vs = MagicMock()
        vs.semantic_search.return_value = [
            {
                "text": "Telecom operators must notify Ofcom of incidents within 24 hours.",
                "metadata": {
                    "doc_id": "ofcom01",
                    "title": "Ofcom Security of Networks",
                    "source_name": "Ofcom",
                    "jurisdiction": "UK",
                    "document_type": "REGULATION",
                    "publication_date": "2023-11-01",
                    "source_url": "https://ofcom.org.uk/security",
                    "content_hash": "c0ffee",
                    "chunk_index": 0,
                    "total_chunks": 2,
                },
                "relevance_score": 0.92,
            }
        ]
        return vs

    def test_query_no_results_returns_fallback(self):
        from rag.chain import RegulatoryRAGChain
        vs = MagicMock()
        vs.semantic_search.return_value = []
        chain = RegulatoryRAGChain.__new__(RegulatoryRAGChain)
        chain.vector_store = vs
        chain.llm = MagicMock()
        result = chain.query("obscure question with no matches")
        assert result["chunks_used"] == 0
        assert "No relevant" in result["answer"]
        assert result["sources"] == []

    @pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
    def test_query_returns_structured_result(self):
        from rag.chain import RegulatoryRAGChain
        from ingestion.vector_store import RegulatoryVectorStore
        vs = MagicMock(spec=RegulatoryVectorStore)
        vs.semantic_search.return_value = [
            {
                "text": "All network operators must implement MFA.",
                "metadata": {
                    "doc_id": "x1",
                    "title": "Security Guidance",
                    "source_name": "NCSC",
                    "jurisdiction": "UK",
                    "document_type": "GUIDANCE",
                    "publication_date": "2024-01-01",
                    "source_url": "https://ncsc.gov.uk/test",
                    "content_hash": "abc",
                    "chunk_index": 0,
                    "total_chunks": 1,
                },
                "relevance_score": 0.9,
            }
        ]
        chain = RegulatoryRAGChain(vs)
        result = chain.query("What are the MFA requirements?")
        assert "answer" in result
        assert isinstance(result["answer"], str)
        assert len(result["answer"]) > 20
        assert "sources" in result
        assert result["chunks_used"] >= 1
