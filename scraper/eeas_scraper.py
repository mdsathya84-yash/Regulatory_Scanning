from datetime import datetime
from typing import List, Optional
from playwright.async_api import Page
from scraper.base_scraper import BaseScraper
from scraper.models import RegulatoryDocument, Jurisdiction, DocumentType


class EEASScraper(BaseScraper):
    """
    Scrapes EU External Action Service sanctions pages.
    https://www.eeas.europa.eu/eeas/european-union-sanctions_en
    """

    INDEX_URL = "https://www.eeas.europa.eu/eeas/european-union-sanctions_en"

    def get_source_name(self) -> str:
        return "EEAS"

    def get_jurisdiction(self):
        return Jurisdiction.EU

    async def scrape_index_page(self) -> List[str]:
        page = await self._context.new_page()
        await page.goto(self.INDEX_URL, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        cookie_btn = await page.query_selector(
            "button[id*='cookie'], button[data-drupal-selector*='cookie-agree']"
        )
        if cookie_btn:
            await cookie_btn.click()
            await page.wait_for_timeout(1000)

        links = await page.eval_on_selector_all(
            "a[href*='sanctions'], a[href*='restrictive-measures'], "
            "a[href*='council-regulation'], a[href*='/eeas/']",
            "els => [...new Set(els.map(e => e.href).filter(h => h.startsWith('http')))]"
        )
        await page.close()
        return links

    async def parse_document_page(self, page: Page, url: str) -> Optional[RegulatoryDocument]:
        try:
            title_el = await page.query_selector("h1, h2.pager__title")
            title = (await title_el.inner_text()).strip() if title_el else "EU Sanctions Update"

            body_el = await page.query_selector(
                ".field--type-text-with-summary, .view-content, article .content, main"
            )
            content = (await body_el.inner_text()).strip() if body_el else ""
            if not content:
                return None

            date_el = await page.query_selector("time[datetime], .date-display-single")
            pub_date = None
            if date_el:
                dt_str = await date_el.get_attribute("datetime") or await date_el.inner_text()
                try:
                    pub_date = datetime.fromisoformat(dt_str[:10])
                except Exception:
                    pass

            multi_j = []
            jurisdiction_keywords = {
                Jurisdiction.UK: ["united kingdom", "uk sanctions"],
                Jurisdiction.US: ["united states", "ofac", "us sanctions"],
                Jurisdiction.APAC: ["china", "russia", "north korea", "iran", "myanmar"],
            }
            for j, keywords in jurisdiction_keywords.items():
                if any(kw in content.lower() for kw in keywords):
                    multi_j.append(j)
            multi_j.append(Jurisdiction.EU)

            return RegulatoryDocument(
                id=self._make_id(url, title),
                title=title,
                content=content,
                source_url=url,
                source_name=self.get_source_name(),
                jurisdiction=Jurisdiction.EU,
                document_type=DocumentType.SANCTION,
                publication_date=pub_date,
                last_scraped=datetime.utcnow(),
                affected_jurisdictions=list(set(multi_j)),
                tags=self._extract_sanction_tags(content),
                content_hash=self._make_content_hash(content),
            )
        except Exception as e:
            print(f"Error parsing EEAS page {url}: {e}")
            return None

    def _extract_sanction_tags(self, content: str) -> List[str]:
        tags = []
        term_map = {
            "asset freeze": "asset-freeze",
            "travel ban": "travel-ban",
            "arms embargo": "arms-embargo",
            "sectoral": "sectoral-sanctions",
            "financial": "financial-sanctions",
        }
        for term, tag in term_map.items():
            if term in content.lower():
                tags.append(tag)
        return tags
