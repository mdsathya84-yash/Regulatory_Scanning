from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional, List
from enum import Enum

class Jurisdiction(str, Enum):
    UK = "UK"
    EU = "EU"
    APAC = "APAC"
    US = "US"
    GLOBAL = "GLOBAL"

class DocumentType(str, Enum):
    REGULATION = "REGULATION"
    DIRECTIVE = "DIRECTIVE"
    SANCTION = "SANCTION"
    GUIDANCE = "GUIDANCE"
    CONSULTATION = "CONSULTATION"
    AMENDMENT = "AMENDMENT"

class RegulatoryDocument(BaseModel):
    id: str                         # SHA-256 hash of URL + title
    title: str
    content: str
    summary: Optional[str] = None
    source_url: HttpUrl
    source_name: str                # e.g. "NCSC", "EEAS", "Ofcom"
    jurisdiction: Jurisdiction
    document_type: DocumentType
    publication_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    last_scraped: datetime
    tags: List[str] = []
    affected_jurisdictions: List[Jurisdiction] = []
    is_amended: bool = False
    amendment_notes: Optional[str] = None
    raw_html: Optional[str] = None
    content_hash: str               # For change detection
