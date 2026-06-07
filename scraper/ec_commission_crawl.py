"""
EC Commission full site crawl
Targets: law, strategy-and-policy, news-and-media, topics, publications (English only)
Outputs: data/ec_commission_pages.csv
"""
import os, sys, re, time, csv, asyncio, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_URL      = "https://commission.europa.eu"
SITEMAP_URL   = f"{BASE_URL}/sitemap.xml"
OUTPUT_CSV    = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ec_commission_pages.csv")
CONCURRENCY   = 20          # parallel requests
REQUEST_DELAY = 0.05        # seconds between batches
TIMEOUT       = 20.0

# Sections to include (regulation-relevant)
TARGET_SECTIONS = {
    "law", "strategy-and-policy", "news-and-media",
    "topics", "publications", "priorities-2024-2029",
    "business-economy-euro", "energy-climate-change-environment",
    "aid-development-cooperation-fundamental-rights",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RegScanner/1.0; +https://github.com/mdsathya84-yash/Regulatory_Scanning)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-GB,en;q=0.9",
}

# ── date extraction helpers ──────────────────────────────────────────────────

_DATE_URL_RE = re.compile(r"_(\d{4}-\d{2}-\d{2})_en$")


def _extract_date(soup: BeautifulSoup, url: str) -> str:
    """Try multiple strategies to get a publication date."""
    # 1. <time datetime="...">
    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        raw = time_tag["datetime"]
        m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
        if m:
            return m.group(1)

    # 2. URL suffix _YYYY-MM-DD_en
    m2 = _DATE_URL_RE.search(url)
    if m2:
        return m2.group(1)

    # 3. meta article:published_time
    for attr in ("property", "name"):
        tag = soup.find("meta", attrs={attr: "article:published_time"})
        if tag and tag.get("content"):
            m3 = re.match(r"(\d{4}-\d{2}-\d{2})", tag["content"])
            if m3:
                return m3.group(1)

    # 4. visible date text near "Published", "Date:" patterns
    for el in soup.select("[class*=date],[class*=Date],[class*=meta]"):
        txt = el.get_text(strip=True)
        m4 = re.search(r"\b(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})\b", txt)
        if m4:
            try:
                return datetime.strptime(m4.group(0), "%d %B %Y").strftime("%Y-%m-%d")
            except ValueError:
                pass

    return ""


def _extract_text(soup: BeautifulSoup) -> str:
    """Pull clean body text from main content area."""
    main = (
        soup.select_one("main article")
        or soup.select_one("main")
        or soup.select_one("[class*=content-block]")
        or soup.find("body")
    )
    if not main:
        return ""
    # Remove nav, footer, scripts, styles
    for tag in main.select("nav, footer, script, style, [class*=cookie], [class*=banner]"):
        tag.decompose()
    text = main.get_text(separator=" ", strip=True)
    # Collapse whitespace
    text = re.sub(r"\s{2,}", " ", text)
    return text[:8000]  # cap at 8k chars per page


def _extract_breadcrumbs(soup: BeautifulSoup) -> list[str]:
    return [
        a.get_text(strip=True)
        for a in soup.select(
            "[class*=breadcrumb] a, [aria-label*=breadcrumb] a, nav[aria-label*=Breadcrumb] a"
        )
    ]


def _infer_regulation_type(breadcrumbs: list[str], section: str, text: str) -> str:
    combined = " ".join(breadcrumbs).lower() + " " + text[:500].lower()
    if "regulation" in combined:
        return "Regulation"
    if "directive" in combined:
        return "Directive"
    if "decision" in combined:
        return "Decision"
    if "recommendation" in combined:
        return "Recommendation"
    if "policy" in combined or "strategy" in section:
        return "Policy/Strategy"
    if "law" in section:
        return "Law/Legislation"
    if "news" in section:
        return "News/Press Release"
    if "publication" in section:
        return "Publication"
    return "General"


# ── sitemap parsing ──────────────────────────────────────────────────────────

def fetch_target_urls() -> list[str]:
    logger.info("Fetching sitemap...")
    r = httpx.get(SITEMAP_URL, headers=HEADERS, timeout=60, verify=False, follow_redirects=True)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    all_urls = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
    logger.info("Sitemap total URLs: %d", len(all_urls))

    filtered = []
    for url in all_urls:
        path = url.replace(BASE_URL + "/", "")
        section = path.split("/")[0]
        # English only, target sections only
        if not url.endswith("_en") and "_en/" not in url and "/en" not in url[-3:]:
            continue
        if section in TARGET_SECTIONS:
            filtered.append(url)

    logger.info("Filtered to %d target URLs", len(filtered))
    return filtered


# ── async page fetcher ───────────────────────────────────────────────────────

async def fetch_page(client: httpx.AsyncClient, url: str) -> dict:
    try:
        r = await client.get(url, follow_redirects=True, timeout=TIMEOUT)
        if r.status_code != 200:
            return {"url": url, "error": f"HTTP {r.status_code}"}

        soup = BeautifulSoup(r.text, "lxml")
        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Skip 404-like pages
        if title.lower() in ("page not found", "404", "error"):
            return {"url": url, "error": "404 page"}

        breadcrumbs = _extract_breadcrumbs(soup)
        date_published = _extract_date(soup, url)
        body_text = _extract_text(soup)

        path = url.replace(BASE_URL + "/", "")
        section = path.split("/")[0]
        reg_type = _infer_regulation_type(breadcrumbs, section, body_text)

        return {
            "regulator": "European Commission",
            "jurisdiction": "EU",
            "section": section,
            "breadcrumb": " > ".join(breadcrumbs),
            "regulation_type": reg_type,
            "title": title,
            "date_published": date_published,
            "url": url,
            "content": body_text,
            "excel_link": f'=HYPERLINK("{url}","{title[:50].replace(chr(34), chr(39))}")',
            "error": "",
        }
    except Exception as e:
        return {"url": url, "error": str(e)[:120]}


async def crawl_all(urls: list[str]) -> list[dict]:
    sem = asyncio.Semaphore(CONCURRENCY)
    results = []
    total = len(urls)

    async def bounded_fetch(client, url):
        async with sem:
            result = await fetch_page(client, url)
            await asyncio.sleep(REQUEST_DELAY)
            return result

    async with httpx.AsyncClient(headers=HEADERS, verify=False) as client:
        tasks = [bounded_fetch(client, url) for url in urls]
        done = 0
        for coro in asyncio.as_completed(tasks):
            row = await coro
            results.append(row)
            done += 1
            if done % 100 == 0 or done == total:
                ok = sum(1 for r in results if not r.get("error"))
                logger.info("Progress: %d/%d  (%d successful)", done, total, ok)

    return results


# ── CSV writer ───────────────────────────────────────────────────────────────

FIELDNAMES = [
    "regulator", "jurisdiction", "section", "breadcrumb",
    "regulation_type", "title", "date_published", "url",
    "content", "excel_link", "error",
]


def save_csv(rows: list[dict]) -> int:
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    good = [r for r in rows if not r.get("error") and r.get("title")]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        w.writerows(good)
    logger.info("Saved %d rows → %s", len(good), OUTPUT_CSV)
    return len(good)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    import warnings
    warnings.filterwarnings("ignore")

    t0 = time.time()
    urls = fetch_target_urls()
    rows = asyncio.run(crawl_all(urls))
    count = save_csv(rows)

    elapsed = time.time() - t0
    errors = sum(1 for r in rows if r.get("error"))
    print(f"\n{'='*60}")
    print(f"  EC Commission crawl complete")
    print(f"  URLs attempted : {len(urls):,}")
    print(f"  Pages saved    : {count:,}")
    print(f"  Errors         : {errors:,}")
    print(f"  Elapsed        : {elapsed:.1f}s")
    print(f"  Output         : {OUTPUT_CSV}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
