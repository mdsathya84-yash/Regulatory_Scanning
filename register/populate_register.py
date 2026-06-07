"""
Rebuild the compliance register from all data sources:
  - EC Commission pages CSV (590 rows)
  - Ofcom Statistical Calendar 2026 (44 rows)
  - ChromaDB regulatory_documents collection (EEAS + Ofcom scraped docs)
Maps each record to: business_unit, associated_risks, risk_level, regulation_type
"""
import os, sys, csv, json, sqlite3, hashlib, re, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH      = os.getenv("REGISTER_DB_PATH", "./data/compliance_register.db")
EC_CSV       = "./data/ec_commission_pages.csv"
OFCOM_CSV    = "./data/ofcom_stats_calendar_2026.csv"
CHROMA_DIR   = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")

# ── BU mapping: (keywords, business_unit) ───────────────────────────────────
BU_RULES = [
    (["privacy","personal data","gdpr","data protection"],               "Technology / Legal / Compliance"),
    (["cyber","cybersecurity","network security","information security"], "Technology / Cybersecurity"),
    (["artificial intelligence","ai act","machine learning","algorithm"], "Technology / AI Governance"),
    (["digital","cloud","software","platform","internet","ecommerce"],   "Technology / Digital"),
    (["telecom","telecommunications","spectrum","mobile","broadband","5g","fixed line","roaming"],
                                                                          "Technology / Network Engineering"),
    (["broadcast","radio","television","tv","media","psb","streaming"],  "Marketing / Broadcasting"),
    (["financial","banking","capital","credit","investment","insurance","payment","euro","monetary","fiscal","budget","tax","customs","treasury"],
                                                                          "Finance / Treasury"),
    (["competition","antitrust","merger","state aid","market power"],    "Legal / Competition"),
    (["sanction","restrictive measure","asset freeze","financial crime","money laundering","aml"],
                                                                          "Legal / Risk / Sanctions"),
    (["health","pharmaceutical","medicine","medical device","hospital","patient","drug","food safety"],
                                                                          "Healthcare / Operations"),
    (["energy","climate","emission","carbon","renewable","environment","green deal","sustainability"],
                                                                          "Operations / Sustainability"),
    (["transport","logistics","shipping","aviation","road","rail","maritime","mobility"],
                                                                          "Operations / Supply Chain"),
    (["agriculture","food","fishery","rural","farm"],                    "Operations / Supply Chain"),
    (["labour","employment","worker","social","welfare","pension","equality","discrimination","hr"],
                                                                          "HR / People"),
    (["consumer","product safety","market surveillance"],                "Operations / Product"),
    (["trade","import","export","customs","tariff"],                     "Operations / Trade"),
    (["justice","criminal","police","court","fundamental rights","rule of law"],
                                                                          "Legal / Compliance"),
    (["foreign","defence","external action","international","geopoliti"],"Legal / Risk / Compliance"),
    (["postal","parcel","delivery","courier"],                           "Operations / Supply Chain / Logistics"),
    (["online safety","child","children","harmful content"],             "Cybersecurity / Legal / Compliance"),
]

# ── Risk mapping: (keywords, risk_label, risk_level) ────────────────────────
RISK_RULES = [
    (["sanction","asset freeze","restrictive measure"], "Sanctions Breach Risk",          "HIGH"),
    (["gdpr","data protection","privacy","personal data"],"Data Privacy & GDPR Risk",     "HIGH"),
    (["cybersecurity","cyber attack","incident","breach"], "Cybersecurity Incident Risk",  "HIGH"),
    (["aml","money laundering","financial crime"],        "Financial Crime Risk",          "HIGH"),
    (["ai act","ai governance","algorithm"],              "AI Governance & Liability Risk","HIGH"),
    (["fine","penalty","infringement","non-compliance"],  "Financial Penalty Risk",        "HIGH"),
    (["directive"],                                       "Implementation Compliance Risk","MEDIUM"),
    (["regulation","regulatory"],                         "Regulatory Non-Compliance Risk","MEDIUM"),
    (["competition","antitrust","merger"],                "Competition Law Risk",          "MEDIUM"),
    (["consumer protection","product safety"],            "Consumer Protection Risk",      "MEDIUM"),
    (["environment","climate","emission"],                "Environmental Compliance Risk", "MEDIUM"),
    (["health","pharmaceutical","medical"],               "Health & Safety Risk",          "MEDIUM"),
    (["trade","customs","tariff"],                        "Trade Compliance Risk",         "MEDIUM"),
    (["labour","employment","worker"],                    "Employment Law Risk",           "MEDIUM"),
    (["telecom","spectrum","broadband"],                  "Regulatory Licence Risk",       "MEDIUM"),
    (["broadcast","media"],                               "Content Regulation Risk",       "LOW"),
    (["publication","report","annual"],                   "Reporting Obligation Risk",     "LOW"),
    (["guidance","recommendation"],                       "Policy Non-Adherence Risk",     "LOW"),
]

DEFAULT_RISK = ("General Regulatory Risk", "LOW")


# Titles that indicate page-level noise rather than regulatory content
_JUNK_TITLE_FRAGMENTS = [
    "cookie", "uses cookie", "store information on your device",
    "page not found", "404", "access denied", "javascript",
    "please enable", "you are being redirected",
]


def _is_junk_title(title: str) -> bool:
    low = title.lower().strip()
    return not low or any(frag in low for frag in _JUNK_TITLE_FRAGMENTS)


def _make_id(source: str, title: str) -> str:
    return hashlib.sha256(f"{source}::{title}".encode()).hexdigest()[:16]


def _match_bu(text: str) -> str:
    low = text.lower()
    for keywords, bu in BU_RULES:
        if any(kw in low for kw in keywords):
            return bu
    return "Legal / Compliance"


def _match_risks(text: str) -> tuple[list[str], str]:
    """Returns (risk_labels, risk_level) — highest level wins."""
    low = text.lower()
    found_risks = []
    found_level = "LOW"
    level_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    for keywords, label, level in RISK_RULES:
        if any(kw in low for kw in keywords):
            if label not in found_risks:
                found_risks.append(label)
            if level_order[level] > level_order[found_level]:
                found_level = level

    if not found_risks:
        found_risks = [DEFAULT_RISK[0]]
        found_level = DEFAULT_RISK[1]

    return found_risks[:4], found_level  # cap at 4 risks


def _clean_date(raw: str) -> str:
    if not raw:
        return ""
    raw = raw.strip()
    # Already YYYY-MM-DD
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    # DD Month YYYY
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw)
    if m:
        try:
            return datetime.strptime(m.group(0), "%d %B %Y").strftime("%Y-%m-%d")
        except ValueError:
            try:
                return datetime.strptime(m.group(0), "%d %b %Y").strftime("%Y-%m-%d")
            except ValueError:
                pass
    return ""


# ── DB helpers ───────────────────────────────────────────────────────────────

def _conn(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db(db_path: str):
    with _conn(db_path) as conn:
        # Add new columns before the index creation (idempotent)
        for col, defn in [
            ("regulation_type", "TEXT"),
            ("risk_level",      "TEXT DEFAULT 'MEDIUM'"),
        ]:
            try:
                conn.execute(f"ALTER TABLE compliance_obligations ADD COLUMN {col} {defn}")
                conn.commit()
            except Exception:
                pass  # column already exists

    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        schema = f.read()
    with _conn(db_path) as conn:
        conn.executescript(schema)


def _upsert(conn, row: dict):
    now = datetime.utcnow().isoformat()
    row.setdefault("created_at", now)
    row["updated_at"] = now
    row["associated_risks"] = json.dumps(row.get("associated_risks", []))
    conn.execute("""
        INSERT INTO compliance_obligations
            (id, title, description, source_doc_id, source_title, source_url,
             source_name, jurisdiction, document_type, regulation_type,
             business_unit, responsible_owner, associated_risks, risk_level,
             effective_date, review_date, status, created_at, updated_at, notes, tags)
        VALUES
            (:id, :title, :description, :source_doc_id, :source_title, :source_url,
             :source_name, :jurisdiction, :document_type, :regulation_type,
             :business_unit, :responsible_owner, :associated_risks, :risk_level,
             :effective_date, :review_date, :status, :created_at, :updated_at, :notes, :tags)
        ON CONFLICT(id) DO UPDATE SET
            description=excluded.description,
            regulation_type=excluded.regulation_type,
            business_unit=excluded.business_unit,
            responsible_owner=excluded.responsible_owner,
            associated_risks=excluded.associated_risks,
            risk_level=excluded.risk_level,
            effective_date=excluded.effective_date,
            status=excluded.status,
            updated_at=excluded.updated_at,
            tags=excluded.tags
    """, row)


# ── Source loaders ────────────────────────────────────────────────────────────

def load_ec_commission(db_path: str) -> int:
    if not os.path.exists(EC_CSV):
        logger.warning("EC CSV not found: %s", EC_CSV)
        return 0

    rows = list(csv.DictReader(open(EC_CSV, encoding="utf-8")))
    count = 0
    now = datetime.utcnow().isoformat()

    # Only import pages that are actual regulatory content
    target_types = {"Regulation", "Directive", "Decision", "Recommendation",
                    "Law/Legislation", "Policy/Strategy", "News/Press Release", "Publication"}

    with _conn(db_path) as conn:
        for row in rows:
            rtype = row.get("regulation_type", "").strip()
            title = row.get("title", "").strip()
            url   = row.get("url", "").strip()
            if not title or not url:
                continue
            if _is_junk_title(title):
                continue
            if rtype not in target_types:
                continue

            text_for_mapping = f"{title} {row.get('breadcrumb','')} {row.get('content','')[:300]}"
            bu = _match_bu(text_for_mapping)
            risks, risk_level = _match_risks(text_for_mapping)
            date = _clean_date(row.get("date_published", ""))

            doc_id = _make_id("ec_commission", url)
            _upsert(conn, {
                "id":               doc_id,
                "title":            title[:250],
                "description":      row.get("content", "")[:500],
                "source_doc_id":    doc_id,
                "source_title":     title[:250],
                "source_url":       url[:500],
                "source_name":      "European Commission",
                "jurisdiction":     "EU",
                "document_type":    rtype,
                "regulation_type":  rtype,
                "business_unit":    bu,
                "responsible_owner":"EU Regulatory Affairs",
                "associated_risks": risks,
                "risk_level":       risk_level,
                "effective_date":   date,
                "review_date":      "",
                "status":           "ACTIVE",
                "notes":            row.get("breadcrumb", "")[:200],
                "tags":             row.get("section", ""),
            })
            count += 1

    logger.info("EC Commission: inserted %d obligations", count)
    return count


def load_ofcom_calendar(db_path: str) -> int:
    if not os.path.exists(OFCOM_CSV):
        logger.warning("Ofcom calendar CSV not found: %s", OFCOM_CSV)
        return 0

    rows = list(csv.DictReader(open(OFCOM_CSV, encoding="utf-8-sig")))
    count = 0

    with _conn(db_path) as conn:
        for row in rows:
            title = (row.get("content") or row.get("regulation") or "").strip()
            if not title or _is_junk_title(title):
                continue

            url  = row.get("regulation_url", "").strip()
            date = _clean_date(row.get("date_published", ""))
            bu   = row.get("impacted_team_function", "").strip() or _match_bu(title)
            text_for_risk = f"{title} {row.get('data_text','')[:200]}"
            risks, risk_level = _match_risks(text_for_risk)

            doc_id = _make_id("ofcom_calendar", title)
            _upsert(conn, {
                "id":               doc_id,
                "title":            title[:250],
                "description":      row.get("data_text", "")[:500],
                "source_doc_id":    doc_id,
                "source_title":     title[:250],
                "source_url":       url or "https://www.ofcom.org.uk/about-ofcom/our-research/statistical-release-calendar-2026",
                "source_name":      "Ofcom",
                "jurisdiction":     "UK",
                "document_type":    "Statistical Release",
                "regulation_type":  "Statistical Release",
                "business_unit":    bu[:200] if bu else "Technology / Network Engineering",
                "responsible_owner":"UK Regulatory Affairs",
                "associated_risks": risks,
                "risk_level":       risk_level,
                "effective_date":   date,
                "review_date":      "",
                "status":           "ACTIVE",
                "notes":            f"Month: {row.get('month','')}",
                "tags":             "ofcom,statistics,2026",
            })
            count += 1

    logger.info("Ofcom calendar: inserted %d obligations", count)
    return count


def load_chroma_docs(db_path: str) -> int:
    """Pull EEAS + Ofcom docs from the regulatory_documents ChromaDB collection."""
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        col = client.get_collection(name="regulatory_documents", embedding_function=ef)
        all_data = col.get(include=["documents", "metadatas"])
    except Exception as e:
        logger.warning("ChromaDB load failed: %s", e)
        return 0

    count = 0
    seen = set()
    now = datetime.utcnow().isoformat()

    with _conn(db_path) as conn:
        for doc, meta in zip(all_data["documents"], all_data["metadatas"]):
            doc_id = meta.get("doc_id", "")
            if doc_id in seen:
                continue
            seen.add(doc_id)

            title    = meta.get("title", "").strip()
            url      = meta.get("source_url", "").strip()
            source   = meta.get("source_name", "Unknown").strip()
            jur      = meta.get("jurisdiction", "EU").strip()
            pub_date = _clean_date(meta.get("publication_date", ""))
            dtype    = meta.get("document_type", "Unknown").strip()

            if not title or _is_junk_title(title):
                continue
            if source in ("European Commission",):
                continue  # skip EC (already loaded from CSV)

            text_for_mapping = f"{title} {dtype} {doc}"[:600]
            bu    = _match_bu(text_for_mapping)
            risks, risk_level = _match_risks(text_for_mapping)

            ob_id = _make_id(source, title)
            _upsert(conn, {
                "id":               ob_id,
                "title":            title[:250],
                "description":      doc[:500],
                "source_doc_id":    doc_id,
                "source_title":     title[:250],
                "source_url":       url[:500],
                "source_name":      source,
                "jurisdiction":     jur,
                "document_type":    dtype,
                "regulation_type":  dtype,
                "business_unit":    bu,
                "responsible_owner": f"{jur} Regulatory Affairs",
                "associated_risks": risks,
                "risk_level":       risk_level,
                "effective_date":   pub_date,
                "review_date":      "",
                "status":           "ACTIVE",
                "notes":            "",
                "tags":             source.lower().replace(" ", "-"),
            })
            count += 1

    logger.info("ChromaDB docs: inserted %d obligations", count)
    return count


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    import warnings
    warnings.filterwarnings("ignore")

    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    _init_db(DB_PATH)

    print("Building compliance register from all sources...")
    n_ec     = load_ec_commission(DB_PATH)
    n_ofcom  = load_ofcom_calendar(DB_PATH)
    n_chroma = load_chroma_docs(DB_PATH)
    total    = n_ec + n_ofcom + n_chroma

    with _conn(DB_PATH) as conn:
        final = conn.execute("SELECT COUNT(*) FROM compliance_obligations").fetchone()[0]
        by_jur = dict(conn.execute(
            "SELECT jurisdiction, COUNT(*) FROM compliance_obligations GROUP BY jurisdiction"
        ).fetchall())
        by_risk = dict(conn.execute(
            "SELECT risk_level, COUNT(*) FROM compliance_obligations GROUP BY risk_level"
        ).fetchall())
        by_bu = conn.execute(
            "SELECT business_unit, COUNT(*) FROM compliance_obligations GROUP BY business_unit ORDER BY COUNT(*) DESC LIMIT 10"
        ).fetchall()

    print(f"\n{'='*60}")
    print(f"  Compliance Register rebuilt")
    print(f"  EC Commission     : {n_ec:>4d}")
    print(f"  Ofcom Calendar    : {n_ofcom:>4d}")
    print(f"  EEAS/Ofcom (DB)   : {n_chroma:>4d}")
    print(f"  Total obligations : {final:>4d}")
    print(f"\n  By Jurisdiction: {dict(by_jur)}")
    print(f"  By Risk Level:   {dict(by_risk)}")
    print(f"\n  Top Business Units:")
    for bu, cnt in by_bu:
        print(f"    {cnt:>4d}  {bu}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
