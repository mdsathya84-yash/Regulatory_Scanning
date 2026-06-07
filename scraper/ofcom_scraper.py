from datetime import datetime
from typing import List, Optional
from playwright.async_api import Page
from scraper.base_scraper import BaseScraper
from scraper.models import RegulatoryDocument, Jurisdiction, DocumentType


class OfcomScraper(BaseScraper):
    """
    Scrapes the UK communications regulator Ofcom (https://www.ofcom.org.uk/).
    Targets:
    - /about-ofcom/latest/media-releases   (press releases)
    - /consultations-and-statements        (consultations and decisions)
    - /research-and-data                   (reports and research)
    """

    INDEX_URLS = [
        "https://www.ofcom.org.uk/about-ofcom/latest/media-releases",
        "https://www.ofcom.org.uk/consultations-and-statements",
        "https://www.ofcom.org.uk/research-and-data",
    ]

    def get_source_name(self) -> str:
        return "Ofcom"

    def get_jurisdiction(self):
        return Jurisdiction.UK

    async def scrape_index_page(self) -> List[str]:
        page = await self._context.new_page()
        all_urls = set()

        for index_url in self.INDEX_URLS:
            try:
                await page.goto(index_url, wait_until="networkidle")

                for _ in range(4):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await page.wait_for_timeout(700)

                links = await page.eval_on_selector_all(
                    "a[href*='/about-ofcom/'], a[href*='/consultations/'], "
                    "a[href*='/research/'], a[href*='/media-releases/'], "
                    "a[href*='/statements/'], a[href*='/decisions/']",
                    "els => [...new Set(els.map(e => e.href).filter(h => h.includes('ofcom.org.uk')))]"
                )
                all_urls.update(links)

                while True:
                    next_btn = await page.query_selector(
                        "a[rel='next'], .pagination-next a, a:has-text('Next')"
                    )
                    if not next_btn:
                        break
                    await next_btn.click()
                    await page.wait_for_load_state("networkidle")
                    links = await page.eval_on_selector_all(
                        "a[href*='/about-ofcom/'], a[href*='/consultations/'], a[href*='/statements/']",
                        "els => els.map(e => e.href)"
                    )
                    all_urls.update(links)
            except Exception as e:
                print(f"Error scraping Ofcom index {index_url}: {e}")

        await page.close()
        return list(all_urls)

    async def parse_document_page(self, page: Page, url: str) -> Optional[RegulatoryDocument]:
        try:
            title_el = await page.query_selector("h1")
            title = (await title_el.inner_text()).strip() if title_el else "Untitled Ofcom Document"

            body_selectors = [
                ".article-body",
                ".content-body",
                "main article",
                "#main-content",
                "main",
            ]
            content = ""
            for sel in body_selectors:
                el = await page.query_selector(sel)
                if el:
                    content = (await el.inner_text()).strip()
                    break

            if not content or len(content) < 100:
                return None

            date_el = await page.query_selector(
                "time[datetime], .publication-date, .date, .meta-date"
            )
            pub_date = None
            if date_el:
                dt_str = (
                    await date_el.get_attribute("datetime")
                    or await date_el.inner_text()
                )
                for fmt in ["%Y-%m-%d", "%d %B %Y", "%B %Y"]:
                    try:
                        pub_date = datetime.strptime(dt_str.strip()[:20], fmt)
                        break
                    except ValueError:
                        continue

            doc_type = self._infer_doc_type(url, content)

            return RegulatoryDocument(
                id=self._make_id(url, title),
                title=title,
                content=content,
                source_url=url,
                source_name=self.get_source_name(),
                jurisdiction=self.get_jurisdiction(),
                document_type=doc_type,
                publication_date=pub_date,
                last_scraped=datetime.utcnow(),
                tags=self._extract_tags(content),
                affected_jurisdictions=[Jurisdiction.UK],
                content_hash=self._make_content_hash(content),
            )
        except Exception as e:
            print(f"Error parsing Ofcom page {url}: {e}")
            return None

    def _infer_doc_type(self, url: str, content: str) -> DocumentType:
        if "consultation" in url or "consultation" in content.lower()[:200]:
            return DocumentType.CONSULTATION
        if "statement" in url or "decision" in url:
            return DocumentType.REGULATION
        if "amendment" in content.lower()[:200]:
            return DocumentType.AMENDMENT
        return DocumentType.GUIDANCE

    def _extract_tags(self, content: str) -> List[str]:
        keywords = [
            "broadband", "spectrum", "broadcasting", "telecoms", "5G",
            "online safety", "net neutrality", "consumer protection",
            "network security", "numbering", "postal services",
            "media plurality", "radio communications",
        ]
        return [kw for kw in keywords if kw.lower() in content.lower()]
