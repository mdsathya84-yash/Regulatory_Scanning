import hashlib
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from scraper.models import RegulatoryDocument
import logging

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """
    Abstract base class for all regulatory website scrapers.

    Subclass this and implement:
    - `scrape_index_page()` — returns list of document URLs to visit
    - `parse_document_page()` — extracts a RegulatoryDocument from a detail page
    - `get_source_name()` — returns the source label (e.g. "NCSC")
    - `get_jurisdiction()` — returns the primary Jurisdiction enum value
    """

    BASE_DELAY_MS = 1500            # Polite delay between requests
    MAX_CONCURRENT_PAGES = 3
    USER_AGENT = (
        "Mozilla/5.0 (compatible; RegulatoryScanner/1.0; "
        "+https://github.com/your-org/regulatory-scanner)"
    )

    def __init__(self, headless: bool = True, timeout_ms: int = 30000):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            user_agent=self.USER_AGENT,
            viewport={"width": 1280, "height": 720},
            java_script_enabled=True,
            accept_downloads=False,
        )
        self._context.set_default_timeout(self.timeout_ms)
        return self

    async def __aexit__(self, *args):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        await self._playwright.stop()

    @abstractmethod
    async def scrape_index_page(self) -> List[str]:
        """Return list of URLs pointing to individual regulatory documents."""
        ...

    @abstractmethod
    async def parse_document_page(self, page: Page, url: str) -> Optional[RegulatoryDocument]:
        """Parse a single document page and return a RegulatoryDocument."""
        ...

    @abstractmethod
    def get_source_name(self) -> str: ...

    @abstractmethod
    def get_jurisdiction(self): ...

    def _make_id(self, url: str, title: str) -> str:
        return hashlib.sha256(f"{url}::{title}".encode()).hexdigest()[:16]

    def _make_content_hash(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()

    async def run(self) -> List[RegulatoryDocument]:
        """Orchestrate full scrape: index → individual pages → models."""
        logger.info(f"[{self.get_source_name()}] Starting scrape...")
        urls = await self.scrape_index_page()
        logger.info(f"[{self.get_source_name()}] Found {len(urls)} document URLs")

        documents = []
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_PAGES)

        async def fetch_one(url: str):
            async with semaphore:
                page = await self._context.new_page()
                try:
                    await page.goto(url, wait_until="networkidle")
                    await asyncio.sleep(self.BASE_DELAY_MS / 1000)
                    doc = await self.parse_document_page(page, url)
                    if doc:
                        documents.append(doc)
                except Exception as e:
                    logger.error(f"[{self.get_source_name()}] Failed to scrape {url}: {e}")
                finally:
                    await page.close()

        await asyncio.gather(*[fetch_one(url) for url in urls])
        logger.info(f"[{self.get_source_name()}] Scraped {len(documents)} documents")
        return documents
