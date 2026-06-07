"""
Ofcom full sub-site crawler.
Fetches all 8 English sitemap XMLs, collects every URL, groups by section,
and writes a CSV where the `content` column contains a clickable HTML hyperlink.

Output: data/ofcom_all_links.csv
Columns: regulator, section, subsection, page_name, url, content, jurisdiction
"""

import asyncio
import csv
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

import httpx

SITEMAPS = [
    ("About Ofcom",              "https://www.ofcom.org.uk/en/aboutofcom_sitemap.xml"),
    ("Internet-Based Services",  "https://www.ofcom.org.uk/en/internetbasedservices_sitemap.xml"),
    ("Media Use & Attitudes",    "https://www.ofcom.org.uk/en/mediauseattitudes_sitemap.xml"),
    ("Online Safety",            "https://www.ofcom.org.uk/en/onlinesafety_sitemap.xml"),
    ("Phones & Broadband",       "https://www.ofcom.org.uk/en/phonebroadband_sitemap.xml"),
    ("Post",                     "https://www.ofcom.org.uk/en/post_sitemap.xml"),
    ("Spectrum",                 "https://www.ofcom.org.uk/en/spectrum_sitemap.xml"),
    ("TV, Radio & On-Demand",    "https://www.ofcom.org.uk/en/tvradioondemand_sitemap.xml"),
]

OUTPUT_CSV = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data", "ofcom_all_links.csv"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def slug_to_title(slug: str) -> str:
    """Convert a URL slug to a human-readable title."""
    return slug.replace("-", " ").replace("_", " ").title()


def parse_url_parts(url: str):
    """
    Given https://www.ofcom.org.uk/about-ofcom/annual-reports/plan
    return (section='about-ofcom', subsection='annual-reports', page='plan', page_name='Plan')
    """
    path = url.replace("https://www.ofcom.org.uk", "").strip("/")
    parts = [p for p in path.split("/") if p]

    section    = slug_to_title(parts[0]) if len(parts) > 0 else ""
    subsection = slug_to_title(parts[1]) if len(parts) > 1 else ""
    page       = slug_to_title(parts[-1]) if parts else ""
    return section, subsection, page


def fetch_sitemap_urls(sitemap_url: str) -> list[str]:
    """Fetch a sitemap XML and return all <loc> URLs."""
    try:
        resp = httpx.get(sitemap_url, headers=HEADERS, timeout=30, follow_redirects=True, verify=False)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
        return urls
    except Exception as e:
        print(f"  ERROR fetching {sitemap_url}: {e}")
        return []


def make_html_link(url: str, label: str) -> str:
    """Return an HTML anchor tag."""
    safe_label = label.replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<a href="{url}" target="_blank">{safe_label}</a>'


def make_excel_hyperlink(url: str, label: str) -> str:
    """Return an Excel HYPERLINK formula."""
    safe_label = label.replace('"', '""')
    safe_url   = url.replace('"', '""')
    return f'=HYPERLINK("{safe_url}","{safe_label}")'


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #

def crawl_all_sitemaps() -> list[dict]:
    rows = []

    for topic_section, sitemap_url in SITEMAPS:
        print(f"Fetching sitemap: {topic_section} ...")
        urls = fetch_sitemap_urls(sitemap_url)
        print(f"  Found {len(urls)} URLs")

        for url in urls:
            section, subsection, page_name = parse_url_parts(url)

            # Human-readable label = last meaningful path segment
            label = page_name if page_name else url

            rows.append({
                "regulator":   "Ofcom",
                "topic":       topic_section,
                "section":     section,
                "subsection":  subsection,
                "page_name":   page_name,
                "url":         url,
                "content":     make_html_link(url, label),
                "excel_link":  make_excel_hyperlink(url, label),
                "jurisdiction": "UK",
            })

    return rows


def save_csv(rows: list[dict], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = [
        "regulator", "topic", "section", "subsection",
        "page_name", "url", "content", "excel_link", "jurisdiction",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {len(rows)} rows -> {path}")


def print_summary(rows: list[dict]):
    from collections import Counter
    counts = Counter(r["topic"] for r in rows)
    total = sum(counts.values())
    print(f"\n{'='*55}")
    print(f"{'OFCOM SITE CRAWL SUMMARY':^55}")
    print(f"{'='*55}")
    print(f"{'Topic Section':<35} {'URLs':>8}")
    print(f"{'-'*55}")
    for topic, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"{topic:<35} {count:>8,}")
    print(f"{'-'*55}")
    print(f"{'TOTAL':<35} {total:>8,}")
    print(f"{'='*55}")


if __name__ == "__main__":
    rows = crawl_all_sitemaps()
    print_summary(rows)
    save_csv(rows, OUTPUT_CSV)
    print(f"\nSample row:")
    if rows:
        r = rows[0]
        for k, v in r.items():
            print(f"  {k:<15} : {v[:80] if len(str(v)) > 80 else v}")
