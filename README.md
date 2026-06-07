# RegScan — AI Regulatory Intelligence Platform

An AI-powered regulatory monitoring system that continuously scrapes UK/EU regulatory sources, indexes documents into a vector database, and exposes a RAG chatbot for natural-language compliance queries.

## Features

- **Automated Scraping** — Playwright-based scrapers for NCSC, EEAS, and Ofcom with polite rate-limiting and pagination
- **RAG Chatbot** — GPT-4o-mini powered Q&A with citation, jurisdiction filters, and source links
- **Compliance Register** — SQLite-backed obligation register linked to BU, owner, jurisdiction, and risk
- **Change Detection** — Hash-based diff detects new and amended regulations on each scrape cycle
- **Alerts** — Slack and email notifications on regulatory changes
- **Multi-jurisdiction Analysis** — Cross-border sanction overlap and impact mapping

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY at minimum
```

### 3. Run the scraping pipeline

```bash
python -m scraper.scheduler
```

### 4. Launch the Streamlit UI

```bash
streamlit run ui/app.py
```

Open [http://localhost:8501](http://localhost:8501)

---

## Docker

```bash
docker-compose up --build
```

---

## Project Structure

```
regulatory-scanner/
├── scraper/          # Playwright scrapers (NCSC, EEAS, Ofcom) + APScheduler
├── ingestion/        # Chunking, embedding, ChromaDB vector store, deduplication
├── rag/              # LangChain RAG chain, retriever, and prompt templates
├── register/         # SQLite compliance obligation register + BU/risk linker
├── alerting/         # Change detection, Slack and email alert senders
├── ui/               # Streamlit multi-page app (chatbot, register, alerts, map)
└── tests/            # Pytest unit and integration tests
```

## Sources Monitored

| Source | Jurisdiction | Document Types |
|--------|-------------|----------------|
| [NCSC](https://www.ncsc.gov.uk) | UK | Guidance, Advisories, Blogs |
| [EEAS](https://www.eeas.europa.eu) | EU | Sanctions, Restrictive Measures |
| [Ofcom](https://www.ofcom.org.uk) | UK | Regulations, Consultations, Statements |

## Running Tests

```bash
# Unit tests only (no API keys needed)
pytest tests/ -v

# Include live scrape tests
RUN_LIVE_TESTS=1 pytest tests/test_scrapers.py -v

# Include OpenAI-backed ingestion/RAG tests
OPENAI_API_KEY=sk-... pytest tests/ -v
```

## Sample Queries

```python
from ingestion.vector_store import RegulatoryVectorStore
from rag.chain import RegulatoryRAGChain

vs = RegulatoryVectorStore()
chain = RegulatoryRAGChain(vs)

chain.query("What cybersecurity obligations apply to telecom operators under UK and EU law?")
chain.query("List all sanctions that include travel bans effective in 2024")
chain.query("What are the most recent NCSC advisories on supply chain security?")
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for embeddings and LLM | Yes |
| `GROQ_API_KEY` | Groq API key (LLM fallback) | No |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL | No |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | Email alert config | No |
| `ALERT_RECIPIENTS` | Comma-separated email list | No |
| `REGISTER_DB_PATH` | SQLite DB path (default: `./data/compliance_register.db`) | No |
| `CHROMA_DB_PATH` | ChromaDB persist path (default: `./data/chroma_db`) | No |
| `SCRAPER_INTERVAL_HOURS` | Scrape frequency in hours (default: 6) | No |
