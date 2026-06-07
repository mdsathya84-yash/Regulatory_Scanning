"""
Links compliance obligations to business units, owners, risk levels,
and jurisdictions using configurable mapping rules.
"""

from typing import Dict, List, Optional
from scraper.models import RegulatoryDocument, Jurisdiction

# Business unit keyword mapping — extend as needed for your org
BU_KEYWORD_MAP: Dict[str, List[str]] = {
    "Network": [
        "network security", "critical infrastructure", "nis2", "nis directive",
        "5g", "broadband", "spectrum", "routing", "bgp", "telecoms network",
    ],
    "Legal & Compliance": [
        "sanctions", "asset freeze", "travel ban", "gdpr", "data protection",
        "lawful interception", "compliance obligation", "regulatory requirement",
    ],
    "Cybersecurity": [
        "cybersecurity", "ransomware", "incident response", "vulnerability",
        "phishing", "malware", "supply chain attack", "authentication",
        "encryption", "penetration testing", "soc", "siem",
    ],
    "Product & Services": [
        "consumer protection", "online safety", "product liability",
        "terms of service", "accessibility", "numbering", "number portability",
    ],
    "Finance": [
        "financial sanctions", "anti-money laundering", "aml", "fraud",
        "financial crime", "payment services",
    ],
}

# Risk keyword → risk label
RISK_KEYWORD_MAP: Dict[str, str] = {
    "mandatory": "Regulatory Non-Compliance",
    "must": "Regulatory Non-Compliance",
    "shall": "Regulatory Non-Compliance",
    "penalty": "Financial Penalty",
    "fine": "Financial Penalty",
    "sanction": "Sanctions Breach",
    "security breach": "Data Breach",
    "personal data": "Data Privacy",
    "critical infrastructure": "Operational Disruption",
    "incident": "Operational Risk",
}

# Owner mapping by jurisdiction
JURISDICTION_OWNER_MAP: Dict[str, str] = {
    "UK": "UK Regulatory Affairs",
    "EU": "EU Regulatory Affairs",
    "US": "North America Compliance",
    "APAC": "APAC Regulatory Affairs",
    "GLOBAL": "Global Head of Compliance",
}


def infer_business_unit(content: str) -> Optional[str]:
    content_lower = content.lower()
    for bu, keywords in BU_KEYWORD_MAP.items():
        if any(kw in content_lower for kw in keywords):
            return bu
    return None


def infer_risks(content: str) -> List[str]:
    content_lower = content.lower()
    risks = []
    for keyword, risk in RISK_KEYWORD_MAP.items():
        if keyword in content_lower and risk not in risks:
            risks.append(risk)
    return risks or ["General Regulatory Risk"]


def infer_owner(jurisdiction: str) -> str:
    return JURISDICTION_OWNER_MAP.get(jurisdiction, "Compliance Team")


def build_obligation_record(
    doc: RegulatoryDocument,
    obligation_title: str,
    description: str,
    effective_date: Optional[str] = None,
) -> Dict:
    """
    Build a complete obligation record dict ready for ObligationRegister.upsert_obligation().
    """
    return {
        "title": obligation_title,
        "description": description,
        "source_doc_id": doc.id,
        "source_title": doc.title,
        "source_url": str(doc.source_url),
        "source_name": doc.source_name,
        "jurisdiction": doc.jurisdiction.value,
        "document_type": doc.document_type.value,
        "business_unit": infer_business_unit(doc.content),
        "responsible_owner": infer_owner(doc.jurisdiction.value),
        "associated_risks": infer_risks(doc.content),
        "effective_date": effective_date or (
            doc.effective_date.date().isoformat() if doc.effective_date else ""
        ),
        "review_date": "",
        "status": "ACTIVE",
        "notes": doc.amendment_notes or "",
        "tags": ",".join(doc.tags),
    }
