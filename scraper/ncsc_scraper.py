from datetime import datetime
from typing import List, Optional
from playwright.async_api import Page
from scraper.base_scraper import BaseScraper
from scraper.models import RegulatoryDocument, Jurisdiction, DocumentType


class NCSCScraper(BaseScraper):
    """
    Scrapes the National Cyber Security Centre (https://www.ncsc.gov.uk/).
    Targets:
    - /guidance              (technical guidance documents)
    - /news                  (advisories and alerts)
    - /collection            (thematic collections)
    - /blog-post             (NCSC blog posts)
    """

    INDEX_URLS = [
        "https://www.ncsc.gov.uk/section/advice-guidance/all-topics",
        "https://www.ncsc.gov.uk/news",
        "https://www.ncsc.gov.uk/section/keep-up-to-date/all-updates",
    ]

    def get_source_name(self) -> str:
        return "NCSC"

    def get_jurisdiction(self):
        return Jurisdiction.UK

    async def scrape_index_page(self) -> List[str]:
        """
        Scrolls through NCSC listing pages and harvests document URLs.
        Handles pagination automatically.
        """
        page = await self._context.new_page()
        all_urls = set()

        for index_url in self.INDEX_URLS:
            try:
                await page.goto(index_url, wait_until="networkidle")

                # Scroll to trigger lazy-load
                for _ in range(5):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await page.wait_for_timeout(800)

                # Collect all article/guidance links
                links = await page.eval_on_selector_all(
                    "a[href*='/guidance/'], a[href*='/news/'], a[href*='/blog-post/'], "
                    "a[href*='/collection/'], a[href*='/report/']",
                    "els => els.map(e => e.href)"
                )
                all_urls.update(links)

                # Follow pagination if present
                while True:
                    next_btn = await page.query_selector("a[rel='next'], .pagination__next")
                    if not next_btn:
                        break
                    await next_btn.click()
                    await page.wait_for_load_state("networkidle")
                    links = await page.eval_on_selector_all(
                        "a[href*='/guidance/'], a[href*='/news/'], a[href*='/blog-post/']",
                        "els => els.map(e => e.href)"
                    )
                    all_urls.update(links)
            except Exception as e:
                print(f"Error scraping index {index_url}: {e}")

        await page.close()
        return list(all_urls)

    async def parse_document_page(self, page: Page, url: str) -> Optional[RegulatoryDocument]:
        try:
            title_el = await page.query_selector("h1")
            title = (await title_el.inner_text()).strip() if title_el else "Untitled"

            body_selectors = [
                ".gem-c-govspeak",
                "article .content",
                "main .body-text",
                "#main-content",
            ]
            content = ""
            for sel in body_selectors:
                el = await page.query_selector(sel)
                if el:
                    content = (await el.inner_text()).strip()
                    break

            if not content:
                return None

            date_text = await page.eval_on_selector(
                "time[datetime], .published-date, .metadata__dates",
                "el => el.getAttribute('datetime') || el.textContent",
            ) if await page.query_selector("time[datetime], .published-date") else None

            pub_date = None
            if date_text:
                for fmt in ["%Y-%m-%d", "%d %B %Y", "%B %d, %Y"]:
                    try:
                        pub_date = datetime.strptime(date_text.strip()[:20], fmt)
                        break
                    except ValueError:
                        continue

            doc_type = DocumentType.GUIDANCE
            if "/news/" in url or "advisory" in content.lower():
                doc_type = DocumentType.GUIDANCE
            if "amendment" in content.lower() or "updated" in title.lower():
                doc_type = DocumentType.AMENDMENT

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
            print(f"Error parsing {url}: {e}")
            return None

    def _extract_tags(self, content: str) -> List[str]:
        keywords = [
            "cybersecurity", "ransomware", "supply chain", "authentication",
            "encryption", "incident response", "vulnerability", "phishing",
            "critical infrastructure", "data protection", "GDPR", "NIS2",
        ]
        return [kw for kw in keywords if kw.lower() in content.lower()]
