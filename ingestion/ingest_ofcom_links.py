"""
Ingest ofcom_all_links.csv into ChromaDB.

Each CSV row → one chunk. Text for embedding is composed from:
  topic + section + subsection + page_name + url

Uses a LOCAL sentence-transformers model (all-MiniLM-L6-v2) stored in a
dedicated 'ofcom_links' collection — no external API calls, no proxy issues.
The main 'regulatory_documents' collection (OpenAI embeddings) is untouched.
"""

import csv
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

import chromadb
from chromadb.utils import embedding_functions

CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ofcom_all_links.csv")
CHROMA_DIR = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
COLLECTION_NAME = "ofcom_links"
BATCH_SIZE = 100  # local model handles large batches fine


def make_id(url: str) -> str:
    return "ofcom_link_" + hashlib.sha256(url.encode()).hexdigest()[:20]


def compose_text(row: dict) -> str:
    """Build a descriptive text string that will be embedded."""
    parts = [
        f"Regulator: {row['regulator']}",
        f"Topic: {row['topic']}",
        f"Section: {row['section']}",
    ]
    if row.get("subsection"):
        parts.append(f"Subsection: {row['subsection']}")
    if row.get("page_name"):
        parts.append(f"Page: {row['page_name']}")
    parts.append(f"URL: {row['url']}")
    parts.append(f"Jurisdiction: {row['jurisdiction']}")
    return " | ".join(parts)


def load_csv_rows(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_chunks(rows: list[dict]) -> list[dict]:
    chunks = []
    for row in rows:
        url = row.get("url", "").strip()
        if not url:
            continue
        chunks.append({
            "id": make_id(url),
            "text": compose_text(row),
            "metadata": {
                "doc_id":      make_id(url),
                "title":       row.get("page_name", ""),
                "source_url":  url,
                "source_name": "Ofcom",
                "jurisdiction": row.get("jurisdiction", "UK"),
                "document_type": "GUIDANCE",
                "publication_date": "",
                "tags": row.get("topic", "").lower().replace(" ", "_").replace(",", ""),
                "affected_jurisdictions": "UK",
                "content_hash": make_id(url),
                "is_amended": "False",
                "chunk_index": 0,
                "total_chunks": 1,
                # Extra fields for richer retrieval
                "topic":       row.get("topic", ""),
                "section":     row.get("section", ""),
                "subsection":  row.get("subsection", ""),
                "content":     row.get("content", ""),       # HTML clickable link
                "excel_link":  row.get("excel_link", ""),
            },
        })
    return chunks


def get_collection():
    """Get or create the ofcom_links ChromaDB collection using local embeddings."""
    print("  Loading local embedding model (all-MiniLM-L6-v2)...", flush=True)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    print(f"  Collection '{COLLECTION_NAME}' ready — current count: {collection.count():,}", flush=True)
    return collection


def ingest(csv_path: str = CSV_PATH):
    print(f"Loading CSV: {csv_path}", flush=True)
    rows = load_csv_rows(csv_path)
    print(f"  {len(rows):,} rows loaded", flush=True)

    chunks = build_chunks(rows)
    print(f"  {len(chunks):,} chunks prepared", flush=True)

    collection = get_collection()

    total_upserted = 0
    batch_num = 0

    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        batch_num += 1
        ids       = [c["id"]       for c in batch]
        documents = [c["text"]     for c in batch]
        metadatas = [c["metadata"] for c in batch]
        try:
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            total_upserted += len(batch)
            pct = total_upserted / len(chunks) * 100
            print(f"  Batch {batch_num:>3} | {total_upserted:>5,}/{len(chunks):,}  ({pct:.1f}%)", flush=True)
        except Exception as e:
            print(f"  ERROR batch {batch_num}: {e}", flush=True)
            time.sleep(2)
            try:
                collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
                total_upserted += len(batch)
                print(f"    Retry OK", flush=True)
            except Exception as e2:
                print(f"    Retry FAILED: {e2} — skipping", flush=True)

    final_count = collection.count()
    print(f"\nDone. Upserted {total_upserted:,} chunks.", flush=True)
    print(f"'{COLLECTION_NAME}' collection now holds {final_count:,} total documents.", flush=True)
    return total_upserted


if __name__ == "__main__":
    ingest()
