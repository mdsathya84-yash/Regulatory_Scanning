"""
Tests for scraper models and base scraper functionality.
Live network tests are skipped unless RUN_LIVE_TESTS=1 is set.
"""

import os
import asyncio
import pytest
from datetime import datetime
from scraper.models import RegulatoryDocument, Jurisdiction, DocumentType


# ---------------------------------------------------------------------------
# Model tests (no network)
# ---------------------------------------------------------------------------

def test_regulatory_document_creation():
    doc = RegulatoryDocument(
        id="abc123",
        title="Test Regulation",
        content="This regulation requires all operators to implement MFA.",
        source_url="https://www.ncsc.gov.uk/guidance/test",
        source_name="NCSC",
        jurisdiction=Jurisdiction.UK,
        document_type=DocumentType.GUIDANCE,
        last_scraped=datetime.utcnow(),
        content_hash="deadbeef",
    )
    assert doc.id == "abc123"
    assert doc.jurisdiction == Jurisdiction.UK
    assert doc.is_amended is False
    assert doc.tags == []


def test_regulatory_document_hash_stability():
    """Same inputs → same content hash."""
    content = "The operator must report incidents within 24 hours."
    import hashlib
    h1 = hashlib.md5(content.encode()).hexdigest()
    h2 = hashlib.md5(content.encode()).hexdigest()
    assert h1 == h2


def test_jurisdiction_enum_values():
    assert Jurisdiction.UK == "UK"
    assert Jurisdiction.EU == "EU"
    assert Jurisdiction.APAC == "APAC"


def test_document_type_enum_values():
    assert DocumentType.SANCTION == "SANCTION"
    assert DocumentType.GUIDANCE == "GUIDANCE"


# ---------------------------------------------------------------------------
# NCSC scraper unit tests
# ---------------------------------------------------------------------------

def test_ncsc_source_name():
    from scraper.ncsc_scraper import NCSCScraper
    s = NCSCScraper()
    assert s.get_source_name() == "NCSC"
    assert s.get_jurisdiction() == Jurisdiction.UK


def test_ncsc_make_id_determinism():
    from scraper.ncsc_scraper import NCSCScraper
    s = NCSCScraper()
    id1 = s._make_id("https://example.com/doc", "My Title")
    id2 = s._make_id("https://example.com/doc", "My Title")
    assert id1 == id2
    assert len(id1) == 16


def test_ncsc_content_hash():
    from scraper.ncsc_scraper import NCSCScraper
    s = NCSCScraper()
    h = s._make_content_hash("some regulatory content")
    assert isinstance(h, str)
    assert len(h) == 32


def test_ncsc_tag_extraction():
    from scraper.ncsc_scraper import NCSCScraper
    s = NCSCScraper()
    tags = s._extract_tags("This document covers ransomware and encryption best practices for cybersecurity.")
    assert "ransomware" in tags
    assert "encryption" in tags
    assert "cybersecurity" in tags


# ---------------------------------------------------------------------------
# EEAS scraper unit tests
# ---------------------------------------------------------------------------

def test_eeas_source_name():
    from scraper.eeas_scraper import EEASScraper
    s = EEASScraper()
    assert s.get_source_name() == "EEAS"
    assert s.get_jurisdiction() == Jurisdiction.EU


def test_eeas_sanction_tag_extraction():
    from scraper.eeas_scraper import EEASScraper
    s = EEASScraper()
    content = "The council imposed an asset freeze and travel ban on designated individuals."
    tags = s._extract_sanction_tags(content)
    assert "asset-freeze" in tags
    assert "travel-ban" in tags
    assert "arms-embargo" not in tags


# ---------------------------------------------------------------------------
# Ofcom scraper unit tests
# ---------------------------------------------------------------------------

def test_ofcom_source_name():
    from scraper.ofcom_scraper import OfcomScraper
    s = OfcomScraper()
    assert s.get_source_name() == "Ofcom"
    assert s.get_jurisdiction() == Jurisdiction.UK


def test_ofcom_doc_type_inference():
    from scraper.ofcom_scraper import OfcomScraper
    s = OfcomScraper()
    assert s._infer_doc_type("https://ofcom.org.uk/consultations/broadband", "consultation about broadband") == DocumentType.CONSULTATION
    assert s._infer_doc_type("https://ofcom.org.uk/statements/5g", "new statement") == DocumentType.REGULATION


# ---------------------------------------------------------------------------
# Live network tests (opt-in)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.getenv("RUN_LIVE_TESTS"), reason="Live tests disabled")
def test_ncsc_live_scrape_returns_documents():
    from scraper.ncsc_scraper import NCSCScraper

    async def _run():
        async with NCSCScraper() as scraper:
            docs = await scraper.run()
        return docs

    docs = asyncio.run(_run())
    assert len(docs) > 0
    assert all(isinstance(d, RegulatoryDocument) for d in docs)
