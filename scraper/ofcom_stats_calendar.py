"""
Scraper for Ofcom Statistical Release Calendar 2026.
URL: https://www.ofcom.org.uk/about-ofcom/our-research/statistical-release-calendar-2026

Output columns:
  regulator, regulation, date_published, excel_urls, regulation_url,
  jurisdiction, impacted_team_function, content, month, data_text
"""

import asyncio
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from playwright.async_api import async_playwright

URL = "https://www.ofcom.org.uk/about-ofcom/our-research/statistical-release-calendar-2026"
OUTPUT_CSV = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data", "ofcom_stats_calendar_2026.csv"
)

# --------------------------------------------------------------------------- #
# Impacted team/function mapping — keyword → team(s)
# --------------------------------------------------------------------------- #
TEAM_MAP = [
    (["broadband", "landline", "telecoms", "telecommunications", "mobile", "5g",
      "spectrum", "network", "fibre"],
     "Technology / Network Engineering"),
    (["complaints", "complaint"],
     "Customer Service / Consumer Affairs"),
    (["pricing", "price", "affordability", "cost"],
     "Finance / Commercial / Strategy"),
    (["postal", "parcel", "post"],
     "Operations / Supply Chain / Logistics"),
    (["online safety", "suspicious", "scam", "fraud", "harm"],
     "Cybersecurity / Legal / Compliance"),
    (["media literacy", "children", "parents", "kids"],
     "Marketing / Digital / Content"),
    (["news consumption", "podcast", "audio", "radio", "television", "broadcast",
      "psm", "psb", "public service"],
     "Broadcasting / Editorial / Media"),
    (["video-on-demand", "vod", "streaming"],
     "Digital / Product / Content"),
    (["access service", "subtitling", "audio description", "signing", "accessibility"],
     "Product / Accessibility / Technology"),
    (["pay-tv", "pay tv"],
     "Commercial / Product / Broadcasting"),
    (["market data", "market share", "market sizing"],
     "Strategy / Regulatory Affairs"),
    (["online experience", "internet user"],
     "Digital / Legal / Compliance"),
    (["sme", "business postal"],
     "Operations / SME Relations"),
    (["community radio", "commercial radio"],
     "Broadcasting / Regulatory Affairs"),
]


def infer_teams(title: str, content: str) -> str:
    text = (title + " " + content).lower()
    matched = []
    for keywords, team in TEAM_MAP:
        if any(kw in text for kw in keywords):
            if team not in matched:
                matched.append(team)
    return "; ".join(matched) if matched else "Regulatory Affairs / Compliance"


# --------------------------------------------------------------------------- #
# Scraper
# --------------------------------------------------------------------------- #
async def scrape_stats_calendar() -> list[dict]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        print(f"Loading {URL} ...")
        await page.goto(URL, wait_until="networkidle", timeout=60000)

        for _ in range(6):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(500)

        data = await page.evaluate("""
            () => {
                const results = [];

                // Collect all tables, tracking the nearest preceding month heading
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_ELEMENT
                );

                let currentMonth = "";
                const processed = new WeakSet();

                function closestMonthHeading(el) {
                    // Walk backwards through siblings/ancestors to find a month heading
                    const MONTHS = /^(January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d{4}$/i;
                    let cur = el;
                    while (cur) {
                        let sib = cur.previousElementSibling;
                        while (sib) {
                            if (/^H[1-4]$/.test(sib.tagName) && MONTHS.test(sib.innerText.trim())) {
                                return sib.innerText.trim();
                            }
                            // Check last heading inside sib
                            const inner = sib.querySelectorAll("h1,h2,h3,h4");
                            for (let i = inner.length - 1; i >= 0; i--) {
                                if (MONTHS.test(inner[i].innerText.trim())) {
                                    return inner[i].innerText.trim();
                                }
                            }
                            sib = sib.previousElementSibling;
                        }
                        cur = cur.parentElement;
                    }
                    return "";
                }

                document.querySelectorAll("table").forEach(table => {
                    if (processed.has(table)) return;
                    processed.add(table);

                    const month = closestMonthHeading(table);

                    const trs = table.querySelectorAll("tbody tr, tr");
                    trs.forEach(tr => {
                        if (tr.querySelector("th")) return;  // skip header rows

                        const cells = tr.querySelectorAll("td");
                        if (cells.length < 2) return;

                        // --- Official Statistic cell ---
                        const statCell = cells[0];
                        const statText = statCell.innerText.replace(/\\s+/g, " ").trim();
                        // Get the href of the first link in the cell (regulation URL)
                        const statLink = statCell.querySelector("a");
                        const regUrl = statLink ? statLink.href : "";

                        // --- Date Published cell ---
                        const dateText = cells[1]
                            ? cells[1].innerText.replace(/\\s+/g, " ").trim()
                            : "";

                        // --- Content cell ---
                        const contentText = cells[2]
                            ? cells[2].innerText.replace(/\\s+/g, " ").trim()
                            : "";

                        // --- Data cell: text + all hrefs ---
                        const dataCell = cells[3];
                        const dataText = dataCell
                            ? dataCell.innerText.replace(/\\s+/g, " ").trim()
                            : "";

                        // Extract all Excel/CSV/XLSX hrefs from data cell
                        const excelLinks = [];
                        if (dataCell) {
                            dataCell.querySelectorAll("a").forEach(a => {
                                const href = a.href || "";
                                const label = a.innerText.trim();
                                // Include XLSX, CSV, XLS, ZIP, PDF links
                                if (href) {
                                    excelLinks.push(href);
                                }
                            });
                        }

                        results.push({
                            month:              month,
                            official_statistic: statText,
                            regulation_url:     regUrl,
                            date_published:     dateText,
                            content:            contentText,
                            data_text:          dataText,
                            excel_urls:         excelLinks.join(" | "),
                        });
                    });
                });

                return results;
            }
        """)

        await browser.close()

    # ---- Post-process -------------------------------------------------------
    months_order = [
        "January","February","March","April","May","June",
        "July","August","September","October","November","December"
    ]
    month_pat = re.compile(
        r"(" + "|".join(months_order) + r")\s+(\d{4})", re.IGNORECASE
    )

    enriched = []
    for row in data:
        if not row.get("official_statistic"):
            continue

        # Fill month if missing
        if not row.get("month"):
            m = month_pat.search(row.get("date_published", ""))
            if m:
                row["month"] = f"{m.group(1).capitalize()} {m.group(2)}"

        # Add fixed fields
        row["regulator"]   = "Ofcom"
        row["jurisdiction"] = "UK"

        # Infer impacted team
        row["impacted_team_function"] = infer_teams(
            row.get("official_statistic", ""),
            row.get("content", ""),
        )

        enriched.append({
            "regulator":              row["regulator"],
            "regulation":             row["official_statistic"],
            "date_published":         row["date_published"],
            "regulation_url":         row.get("regulation_url", ""),
            "excel_urls":             row.get("excel_urls", ""),
            "jurisdiction":           row["jurisdiction"],
            "impacted_team_function": row["impacted_team_function"],
            "content":                row.get("content", ""),
            "month":                  row.get("month", ""),
            "data_text":              row.get("data_text", ""),
        })

    # Sort chronologically
    def sort_key(r):
        parts = r.get("month", "").split()
        if len(parts) == 2:
            mo = {m: i for i, m in enumerate(months_order)}
            return (int(parts[1]), mo.get(parts[0], 99))
        return (9999, 99)

    enriched.sort(key=sort_key)
    return enriched


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #
def save_csv(rows: list[dict], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = [
        "regulator", "regulation", "date_published", "regulation_url",
        "excel_urls", "jurisdiction", "impacted_team_function",
        "content", "month", "data_text",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {len(rows)} rows -> {path}")


def print_table(rows: list[dict]):
    if not rows:
        print("No rows extracted.")
        return

    cols = [
        ("regulation",             35),
        ("date_published",         22),
        ("regulation_url",         45),
        ("excel_urls",             40),
        ("jurisdiction",           12),
        ("impacted_team_function", 38),
    ]

    def trunc(s, n):
        s = s or ""
        return s if len(s) <= n else s[:n-1] + "..."

    sep = "+" + "+".join("-" * (w + 2) for _, w in cols) + "+"
    fmt = "| " + " | ".join(f"{{:<{w}}}" for _, w in cols) + " |"
    headers = [trunc(k.replace("_", " ").title(), w) for k, w in cols]

    current_month = None
    for row in rows:
        if row.get("month") != current_month:
            current_month = row.get("month", "")
            print(f"\n{'='*60}\n  {current_month}\n{'='*60}")
            print(sep)
            print(fmt.format(*headers))
            print(sep)
        print(fmt.format(*[trunc(row.get(k, ""), w) for k, w in cols]))
        print(sep)


if __name__ == "__main__":
    rows = asyncio.run(scrape_stats_calendar())
    if rows:
        print_table(rows)
        save_csv(rows, OUTPUT_CSV)
        print(f"Total records: {len(rows)}")
    else:
        print("No data extracted. Page structure may have changed.")
