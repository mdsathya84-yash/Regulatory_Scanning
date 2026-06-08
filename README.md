# ⚖️ RegScan — AI-Powered Regulatory Intelligence Platform

> *Turning regulatory complexity into actionable business intelligence*

---

## 📌 Slide 1 — The Problem

Organisations operating across UK and EU markets face an ever-growing volume of regulations, directives, and sanctions. Keeping up manually is slow, error-prone, and costly.

**Key challenges:**
- Regulatory publications are fragmented across dozens of government websites
- Teams spend days manually tracking changes across NCSC, Ofcom, EEAS, and the European Commission
- No single view links a regulation to the business unit it affects or the risk it carries
- Sanctions and directives published in Brussels can have immediate UK operational impact — and vice versa

---

## 🎯 Slide 2 — What RegScan Does

RegScan is an **AI-powered regulatory monitoring and Q&A platform** that automatically:

1. **Scrapes** regulatory publications daily from UK and EU sources
2. **Indexes** content into a searchable AI knowledge base (6,500+ document chunks)
3. **Maps** every regulation to a Business Unit, Risk Level, and Jurisdiction
4. **Answers** plain-English compliance questions in seconds using AI

> **Bottom line:** What used to take a compliance team days now takes minutes.

---

## 🌐 Slide 3 — Sources Monitored

| Source | Jurisdiction | Coverage |
|--------|-------------|----------|
| 🇬🇧 **NCSC** | United Kingdom | Cyber guidance, threat advisories, security frameworks |
| 🇬🇧 **Ofcom** | United Kingdom | Telecoms, broadcasting, online safety, spectrum regulation |
| 🇪🇺 **EEAS** | European Union | Sanctions, restrictive measures, foreign policy instruments |
| 🇪🇺 **European Commission** | European Union | Regulations, Directives, Decisions, Policies across all departments |

**Monitoring frequency:** Continuous · **Total regulations indexed:** 6,500+ document chunks · **Obligations tracked:** 698

---

## 📊 Slide 4 — Compliance Obligation Register

A live register of **698 compliance obligations** extracted from all monitored sources.

Every obligation is tagged with:

| Field | Example |
|-------|---------|
| **Regulation Title** | EU AI Act · NIS2 Directive · Ofcom Broadband Statement |
| **Regulation Type** | Regulation · Directive · Decision · Recommendation |
| **Date Issued** | 2025-10-21 |
| **Jurisdiction** | EU · UK |
| **Impacted Business Unit** | Technology / AI Governance · Finance / Treasury · Legal / Compliance |
| **Associated Risk** | AI Governance Risk · Sanctions Breach Risk · Data Privacy Risk |
| **Risk Level** | 🔴 HIGH · 🟡 MEDIUM · 🟢 LOW |
| **Source URL** | Clickable link to original publication |

**Risk breakdown across 698 obligations:**
- 🔴 HIGH risk — 125 obligations (financial penalties, sanctions breach, GDPR, cybersecurity)
- 🟡 MEDIUM risk — 213 obligations (directives, regulatory non-compliance)
- 🟢 LOW risk — 360 obligations (publications, guidance, reporting requirements)

---

## 💬 Slide 5 — AI Compliance Chatbot

Ask questions in plain English — RegScan retrieves relevant regulations and provides structured answers with source citations.

**Sample questions teams are asking:**

| Business Need | Example Question |
|--------------|-----------------|
| Regulatory change tracking | *"List new EU regulations and directives published in 2025"* |
| Sanctions exposure | *"What sanctions apply to Russia under EU and UK law?"* |
| AI governance | *"What does the EU AI Act require from high-risk AI systems?"* |
| Cyber obligations | *"What cybersecurity requirements apply to telecom operators under NIS2?"* |
| Financial compliance | *"What are the DORA requirements for financial institutions?"* |
| Data privacy | *"What are our data protection obligations under EU GDPR?"* |

**Powered by:** Groq LLaMA-3.3-70b · Retrieval-Augmented Generation (RAG) · Local vector search

---

## 🏢 Slide 6 — Business Unit Coverage

RegScan automatically maps every regulation to the team responsible for it.

| Business Unit | Key Regulations Tracked |
|--------------|------------------------|
| **Finance / Treasury** | DORA, ECB rules, budget regulations, fiscal frameworks |
| **Technology / Cybersecurity** | NIS2, Cyber Resilience Act, NCSC advisories |
| **Technology / AI Governance** | EU AI Act, algorithmic accountability rules |
| **Legal / Risk / Sanctions** | EEAS sanctions, OFSI restrictive measures |
| **Marketing / Broadcasting** | Ofcom broadcasting codes, PSB obligations |
| **Technology / Network Engineering** | Ofcom spectrum, broadband, 5G licensing |
| **Operations / Sustainability** | EU Green Deal, emissions regulations |
| **HR / People** | Employment directives, equality legislation |

---

## 🔒 Slide 7 — Risk Framework

Risks are automatically assigned based on regulation content and type.

**HIGH Risk triggers:**
- Sanctions breach · GDPR / data protection violations · Cybersecurity incidents
- AML / financial crime · AI governance failures · Financial penalties

**MEDIUM Risk triggers:**
- EU Directive implementation deadlines · Regulatory non-compliance
- Competition law · Consumer protection · Trade compliance

**LOW Risk triggers:**
- Annual reporting obligations · Policy guidance · Recommendations

---

## 🛠️ Slide 8 — How It Works (Technical Summary)

```
Regulatory Websites  →  Daily Scrapers  →  AI Knowledge Base  →  Chatbot / Register
(NCSC, Ofcom, EC,         (Automated)       (ChromaDB +             (Streamlit UI)
 EEAS)                                        Embeddings)
```

| Component | Technology |
|-----------|-----------|
| **Web Scraping** | Playwright + httpx (async, 20 concurrent requests) |
| **AI Knowledge Base** | ChromaDB vector store · `all-MiniLM-L6-v2` local embeddings |
| **LLM / Chatbot** | Groq `llama-3.3-70b-versatile` (RAG-augmented) |
| **Obligation Register** | SQLite database · 698 obligations · keyword-mapped BU + risk |
| **User Interface** | Streamlit web app · accessible at http://localhost:8501 |
| **Deployment** | Docker-ready · runs on Windows / Linux / Mac |

---

## 📈 Slide 9 — Current Coverage Snapshot

| Metric | Value |
|--------|-------|
| Total document chunks indexed | 6,500+ |
| Compliance obligations in register | 698 |
| EU obligations | 646 |
| UK obligations | 52 |
| Regulation types tracked | 10 (Regulation, Directive, Decision…) |
| Business units mapped | 16 |
| Data sources | 4 (NCSC, Ofcom, EEAS, EC) |
| Ofcom statistical releases (2026) | 44 |
| EC Commission pages indexed | 589 |

---

## 🚀 Slide 10 — Roadmap & Next Steps

**Immediate opportunities:**
- [ ] Add OFAC (US sanctions) as a 5th data source
- [ ] Add EUR-Lex for full EU legislative text coverage
- [ ] Email / Slack alerts when high-risk regulations are published
- [ ] Scheduled daily digest report for compliance teams

**Medium-term:**
- [ ] Role-based access — different BU views for different teams
- [ ] Obligation assignment workflow — assign regulations to named owners
- [ ] Integration with GRC (Governance, Risk & Compliance) tools
- [ ] Automated horizon-scanning report (PDF export)

**Future:**
- [ ] US (OFAC, FTC, FCC) and APAC (PDPA, PIPL) jurisdictions
- [ ] Cross-border impact scoring — quantify overlap between regimes
- [ ] Regulation change diff alerts — what changed between versions

---

## ⚙️ Slide 11 — Setup & Access (IT Reference)

```bash
# 1. Clone and install
git clone https://github.com/mdsathya84-yash/Regulatory_Scanning
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Set GROQ_API_KEY in .env

# 3. Run
streamlit run ui/app.py
# Open http://localhost:8501
```

**Or with Docker:**
```bash
docker-compose up --build
```

**Environment variables required:**

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | LLM for chatbot answers |
| `CHROMA_DB_PATH` | Vector database location |
| `REGISTER_DB_PATH` | Compliance obligation register |

---

*RegScan · Built with Streamlit, ChromaDB, Groq LLaMA-3.3-70b · Sources: NCSC · Ofcom · EEAS · European Commission*
