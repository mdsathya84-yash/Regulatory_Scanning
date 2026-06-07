import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
import hashlib
import os

DB_PATH = os.getenv("REGISTER_DB_PATH", "./data/compliance_register.db")


class ObligationRegister:
    """
    SQLite-backed compliance obligation register.
    Maps each obligation to source regulation, BU, owner, risk, and jurisdiction.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path) as f:
            schema = f.read()
        with self._conn() as conn:
            conn.executescript(schema)

    def upsert_obligation(self, data: Dict[str, Any]) -> str:
        """Create or update a compliance obligation. Returns obligation ID."""
        ob_id = hashlib.sha256(
            f"{data['source_doc_id']}::{data['title']}".encode()
        ).hexdigest()[:16]

        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO compliance_obligations
                    (id, title, description, source_doc_id, source_title, source_url,
                     source_name, jurisdiction, document_type, business_unit,
                     responsible_owner, associated_risks, effective_date, review_date,
                     status, created_at, updated_at, notes, tags)
                VALUES
                    (:id, :title, :description, :source_doc_id, :source_title, :source_url,
                     :source_name, :jurisdiction, :document_type, :business_unit,
                     :responsible_owner, :associated_risks, :effective_date, :review_date,
                     :status, :created_at, :updated_at, :notes, :tags)
                ON CONFLICT(id) DO UPDATE SET
                    description=excluded.description,
                    responsible_owner=excluded.responsible_owner,
                    associated_risks=excluded.associated_risks,
                    effective_date=excluded.effective_date,
                    review_date=excluded.review_date,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    notes=excluded.notes,
                    tags=excluded.tags
            """, {
                "id": ob_id,
                "created_at": now,
                "updated_at": now,
                "associated_risks": json.dumps(data.get("associated_risks", [])),
                **{k: v for k, v in data.items() if k != "associated_risks"},
            })
        return ob_id

    def search(
        self,
        jurisdiction: Optional[str] = None,
        business_unit: Optional[str] = None,
        status: Optional[str] = "ACTIVE",
        keyword: Optional[str] = None,
        risk_level: Optional[str] = None,
        regulation_type: Optional[str] = None,
    ) -> List[Dict]:
        sql = "SELECT * FROM compliance_obligations WHERE 1=1"
        params = []

        if status:
            sql += " AND status = ?"
            params.append(status)
        if jurisdiction:
            sql += " AND jurisdiction = ?"
            params.append(jurisdiction)
        if business_unit:
            sql += " AND business_unit LIKE ?"
            params.append(f"%{business_unit}%")
        if risk_level:
            sql += " AND risk_level = ?"
            params.append(risk_level)
        if regulation_type:
            sql += " AND (regulation_type = ? OR document_type = ?)"
            params.extend([regulation_type, regulation_type])
        if keyword:
            sql += " AND (title LIKE ? OR description LIKE ? OR tags LIKE ? OR business_unit LIKE ?)"
            params.extend([f"%{keyword}%"] * 4)

        sql += " ORDER BY effective_date DESC NULLS LAST, title ASC"

        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_by_id(self, obligation_id: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM compliance_obligations WHERE id = ?", (obligation_id,)
            ).fetchone()
        return dict(row) if row else None

    def mark_superseded(self, obligation_id: str, notes: str = ""):
        with self._conn() as conn:
            conn.execute(
                "UPDATE compliance_obligations SET status='SUPERSEDED', updated_at=?, notes=? WHERE id=?",
                (datetime.utcnow().isoformat(), notes, obligation_id),
            )

    def stats(self) -> Dict[str, Any]:
        """Return summary statistics for the register."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM compliance_obligations").fetchone()[0]
            by_jurisdiction = dict(
                conn.execute(
                    "SELECT jurisdiction, COUNT(*) FROM compliance_obligations GROUP BY jurisdiction"
                ).fetchall()
            )
            by_status = dict(
                conn.execute(
                    "SELECT status, COUNT(*) FROM compliance_obligations GROUP BY status"
                ).fetchall()
            )
            by_risk = dict(
                conn.execute(
                    "SELECT risk_level, COUNT(*) FROM compliance_obligations GROUP BY risk_level"
                ).fetchall()
            )
            by_type = dict(
                conn.execute(
                    "SELECT regulation_type, COUNT(*) FROM compliance_obligations "
                    "WHERE regulation_type IS NOT NULL GROUP BY regulation_type ORDER BY COUNT(*) DESC LIMIT 10"
                ).fetchall()
            )
        return {
            "total": total,
            "by_jurisdiction": by_jurisdiction,
            "by_status": by_status,
            "by_risk": by_risk,
            "by_type": by_type,
        }
