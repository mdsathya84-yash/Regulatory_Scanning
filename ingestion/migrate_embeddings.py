"""
Migrate 'regulatory_documents' collection from OpenAI embeddings
to local sentence-transformers (all-MiniLM-L6-v2).

Steps:
  1. Read all docs + metadata from the existing collection
  2. Delete the collection
  3. Recreate it with the local embedding function
  4. Re-upsert all docs (re-embedded locally)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv()

import chromadb
from chromadb.utils import embedding_functions

CHROMA_DIR   = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
COLLECTION   = "regulatory_documents"
MODEL        = "all-MiniLM-L6-v2"
BATCH_SIZE   = 100


def migrate():
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # --- 1. Read everything from existing collection (no embedding fn needed for get()) ---
    print(f"Reading existing '{COLLECTION}' collection...", flush=True)
    old_col = client.get_collection(name=COLLECTION)
    total = old_col.count()
    print(f"  {total:,} documents found", flush=True)

    all_data = old_col.get(include=["documents", "metadatas"])
    ids       = all_data["ids"]
    documents = all_data["documents"]
    metadatas = all_data["metadatas"]
    print(f"  Retrieved {len(ids):,} records", flush=True)

    # --- 2. Delete old collection ---
    print("Deleting old collection...", flush=True)
    client.delete_collection(name=COLLECTION)
    print("  Done", flush=True)

    # --- 3. Recreate with local embedding function ---
    print(f"Creating new '{COLLECTION}' with {MODEL}...", flush=True)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL)
    new_col = client.create_collection(
        name=COLLECTION,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    print("  Collection created", flush=True)

    # --- 4. Re-upsert in batches ---
    print(f"Re-embedding {len(ids):,} docs locally...", flush=True)
    upserted = 0
    for start in range(0, len(ids), BATCH_SIZE):
        end = start + BATCH_SIZE
        new_col.upsert(
            ids=ids[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )
        upserted += len(ids[start:end])
        pct = upserted / len(ids) * 100
        print(f"  {upserted:>5,}/{len(ids):,}  ({pct:.1f}%)", flush=True)

    print(f"\nMigration complete. '{COLLECTION}' now has {new_col.count():,} docs "
          f"with local {MODEL} embeddings.", flush=True)


if __name__ == "__main__":
    migrate()
