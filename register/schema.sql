CREATE TABLE IF NOT EXISTS compliance_obligations (
    id                TEXT PRIMARY KEY,
    title             TEXT NOT NULL,
    description       TEXT,
    source_doc_id     TEXT NOT NULL,
    source_title      TEXT NOT NULL,
    source_url        TEXT NOT NULL,
    source_name       TEXT NOT NULL,
    jurisdiction      TEXT NOT NULL,
    document_type     TEXT NOT NULL,
    regulation_type   TEXT,
    business_unit     TEXT,
    responsible_owner TEXT,
    associated_risks  TEXT,          -- JSON array of risk strings
    risk_level        TEXT DEFAULT 'MEDIUM',   -- HIGH | MEDIUM | LOW
    effective_date    TEXT,
    review_date       TEXT,
    status            TEXT DEFAULT 'ACTIVE',   -- ACTIVE | UNDER_REVIEW | SUPERSEDED
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    notes             TEXT,
    tags              TEXT           -- comma-separated
);

CREATE INDEX IF NOT EXISTS idx_jurisdiction     ON compliance_obligations(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_business_unit    ON compliance_obligations(business_unit);
CREATE INDEX IF NOT EXISTS idx_status           ON compliance_obligations(status);
CREATE INDEX IF NOT EXISTS idx_effective_date   ON compliance_obligations(effective_date);
CREATE INDEX IF NOT EXISTS idx_regulation_type  ON compliance_obligations(regulation_type);
CREATE INDEX IF NOT EXISTS idx_risk_level       ON compliance_obligations(risk_level);
