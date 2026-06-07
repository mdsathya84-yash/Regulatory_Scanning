"""
Ingest EC Commission pages CSV into ChromaDB collection 'ec_regulations'.
Chunks long body text, stores metadata for regulation_type, date, jurisdiction, URL.
"""
import os, sys, re, csv, hashlib, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import chromadb
from chromadb.utils import embedding_functions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CSV_PATH      = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ec_commission_pages.csv")
CHROMA_DIR    = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
COLLECTION    = "ec_regulations"
MODEL         = "all-MiniLM-L6-v2"
CHUNK_SIZE    = 800    # chars
CHUNK_OVERLAP = 150
BATCH_SIZE    = 100


# ── chunker ──────────────────────────────────────────────────────────────────

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping character-level chunks."""
    if not text or len(text) <= size:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def make_id(url: str, chunk_idx: int) -> str:
    h = hashlib.md5(url.encode()).hexdigest()[:12]
    return f"ec_{h}_{chunk_idx}"


# ── reader ───────────────────────────────────────────────────────────────────

def load_csv(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("title") and row.get("url"):
                rows.append(row)
    logger.info("Loaded %d rows from %s", len(rows), path)
    return rows


# ── ingestor ─────────────────────────────────────────────────────────────────

def ingest(rows: list[dict]) -> int:
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL)
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # Drop and recreate to avoid stale data
    try:
        client.delete_collection(name=COLLECTION)
        logger.info("Deleted existing '%s' collection", COLLECTION)
    except Exception:
        pass

    col = client.create_collection(
        name=COLLECTION,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("Created collection '%s'", COLLECTION)

    ids, docs, metas = [], [], []
    total_chunks = 0

    for row in rows:
        content = (row.get("content") or "").strip()
        title   = (row.get("title") or "").strip()

        # Build chunks; always include at least a title-only chunk
        text_chunks = chunk_text(content) if content else []
        if not text_chunks:
            text_chunks = [title]

        for idx, chunk in enumerate(text_chunks):
            # Embed: prepend title for better retrieval
            embed_text = f"{title}\n{chunk}" if idx > 0 else chunk

            ids.append(make_id(row["url"], idx))
            docs.append(embed_text)
            metas.append({
                "doc_id":          make_id(row["url"], 0),
                "chunk_index":     idx,
                "title":           title[:200],
                "url":             row.get("url", "")[:500],
                "regulator":       row.get("regulator", "European Commission"),
                "jurisdiction":    row.get("jurisdiction", "EU"),
                "section":         row.get("section", ""),
                "breadcrumb":      row.get("breadcrumb", "")[:300],
                "regulation_type": row.get("regulation_type", ""),
                "date_published":  row.get("date_published", ""),
                "source_name":     "European Commission",
                "source_url":      row.get("url", "")[:500],
                "publication_date": row.get("date_published", ""),
            })
            total_chunks += 1

        # Batch upsert
        if len(ids) >= BATCH_SIZE:
            col.upsert(ids=ids, documents=docs, metadatas=metas)
            ids, docs, metas = [], [], []

    if ids:
        col.upsert(ids=ids, documents=docs, metadatas=metas)

    final_count = col.count()
    logger.info("Ingestion complete: %d chunks in '%s'", final_count, COLLECTION)
    return final_count


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    import warnings
    warnings.filterwarnings("ignore")

    if not os.path.exists(CSV_PATH):
        print(f"ERROR: CSV not found at {CSV_PATH}")
        print("Run scraper/ec_commission_crawl.py first.")
        sys.exit(1)

    rows = load_csv(CSV_PATH)
    count = ingest(rows)

    print(f"\n{'='*60}")
    print(f"  EC Regulations ingestion complete")
    print(f"  Pages ingested : {len(rows):,}")
    print(f"  Chunks stored  : {count:,}")
    print(f"  Collection     : {COLLECTION}")
    print(f"  ChromaDB path  : {CHROMA_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
