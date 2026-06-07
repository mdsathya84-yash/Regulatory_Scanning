from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from scraper.models import RegulatoryDocument


class RegulatoryChunker:
    """
    Chunks regulatory documents into overlapping segments suitable
    for embedding, preserving all metadata per chunk.
    """

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def chunk(self, doc: RegulatoryDocument) -> List[Dict[str, Any]]:
        chunks = self.splitter.split_text(doc.content)
        return [
            {
                "id": f"{doc.id}_chunk_{i}",
                "text": chunk,
                "metadata": {
                    "doc_id": doc.id,
                    "title": doc.title,
                    "source_url": str(doc.source_url),
                    "source_name": doc.source_name,
                    "jurisdiction": doc.jurisdiction.value,
                    "document_type": doc.document_type.value,
                    "publication_date": doc.publication_date.isoformat() if doc.publication_date else "",
                    "tags": ",".join(doc.tags),
                    "affected_jurisdictions": ",".join(j.value for j in doc.affected_jurisdictions),
                    "content_hash": doc.content_hash,
                    "is_amended": str(doc.is_amended),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            }
            for i, chunk in enumerate(chunks)
        ]
