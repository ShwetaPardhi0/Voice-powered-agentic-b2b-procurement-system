# 🏭 Voice-Powered Agentic B2B Inventory Control Tower

A **production-grade, voice-powered multi-agent AI system** that autonomously orchestrates end-to-end B2B procurement workflows — from real-time voice commands to supplier selection, risk assessment, purchase order generation, Slack-based approvals, and automated manager escalations.

> **Stack**: LiveKit WebRTC · Deepgram STT · Gemini 2.5 Flash · ElevenLabs TTS · LangGraph · PostgreSQL + pgvector · Redis · FastAPI · Slack Block Kit

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│             LiveKit WebRTC Real-Time Voice Engine                   │
│   Deepgram Nova-2 (STT)  ──▶  Gemini 2.5 Flash (LLM/Function Call) │
│                               ──▶  ElevenLabs (TTS Streaming)      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  LangGraph Multi-Agent Supervisor                   │
│   ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────────────┐  │
│   │ Inventory │ │ Supplier  │ │   Risk    │ │   Procurement     │  │
│   │   Agent   │ │   Agent   │ │   Agent   │ │      Agent        │  │
│   └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └────────┬──────────┘  │
└─────────┼─────────────┼─────────────┼────────────────┼─────────────┘
          │             │             │                │
          ▼             ▼             ▼                ▼
┌──────────────────────────────────┐  ┌───────────────────────────────┐
│   PostgreSQL + pgvector          │  │   Slack Approval Workflow      │
│   (Source of Truth & RAG Store)  │  │   Email Notifications          │
│                                  │  │   Reminder & Escalation Engine │
└──────────────────────────────────┘  └───────────────────────────────┘
```

---

## ⚙️ Core Subsystems

### 🎙️ Voice Pipeline (`voice/`)
| Component | Technology |
|-----------|-----------|
| Real-Time Transport | LiveKit WebRTC Worker |
| Speech-to-Text | Deepgram Nova-2 |
| Language Model | Gemini 2.5 Flash (function calling) |
| Text-to-Speech | ElevenLabs streaming synthesis |

### 🤖 Multi-Agent System (`agents/`)
| Agent | Responsibility |
|-------|---------------|
| **Supervisor** | Routes tasks to sub-agents based on intent |
| **Inventory Agent** | Checks real-time stock levels, reorder points, safety stock |
| **Supplier Agent** | Evaluates quotes, pricing tiers, lead time, MOQ |
| **Risk Agent** | Grades supplier reliability, contract compliance, supply chain risk |
| **Procurement Agent** | PO creation, ₹25,000 threshold routing, PostgreSQL status updates |

### 📚 RAG System (`rag/`)
- **Vector Store**: PostgreSQL with `pgvector` extension
- **Embeddings**: Gemini `text-embedding-004`
- **Documents**: Supplier contracts, SLAs, penalty clauses, shipping policies, product catalogs

### 🔔 Slack Approval Workflow (`services/`)
- Auto-approves POs **≤ ₹25,000** → inventory updated immediately
- POs **> ₹25,000** → Slack Block Kit card with **[🔍 View PO] [🟢 Approve] [🔴 Reject]**
- Manager receives HTML email notification with PO details
- **Signature Verification**: `SLACK_SIGNING_SECRET` protects the webhook from forged requests
- **Duplicate Action Guard**: Terminal states (`APPROVED`/`REJECTED`) cannot be overwritten

### ⏰ Reminder & Escalation Engine (`services/reminder_service.py`)
| Day | Action |
|-----|--------|
| Day 0 | Initial Slack notification + Manager Email |
| Day 1 | Day 1 Reminder (Slack + Email) |
| Day 2 | Day 2 Final Reminder (Slack + Email) |
| Day 3 | Escalate → Mark `OVERDUE` in PostgreSQL, update Slack card ⚠️ |

> **Rule**: `OVERDUE` status **never** updates inventory. Reminders stop immediately on `APPROVED`/`REJECTED`.

---

## 🔧 Environment Setup

Copy `.env.example` to `.env` and fill in your credentials:

```ini
# --- Google Gemini ---
GOOGLE_API_KEY=your_google_api_key
MODEL=gemini-2.5-flash
EMBEDDING_MODEL=text-embedding-004

# --- PostgreSQL ---
DB_HOST=localhost
DB_PORT=5433
DB_NAME=procurement_ai
DB_USER=postgres
DB_PASSWORD=yourpassword

# --- Redis ---
REDIS_HOST=localhost
REDIS_PORT=6379

# --- LiveKit ---
LIVEKIT_URL=wss://your-app.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# --- Deepgram ---
DEEPGRAM_API_KEY=your_deepgram_key

# --- ElevenLabs ---
ELEVENLABS_API_KEY=your_elevenlabs_key
ELEVENLABS_VOICE_ID=your_voice_id

# --- Slack ---
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_CHANNEL_ID=C0XXXXXXXXX
SLACK_SIGNING_SECRET=your_signing_secret

# --- Email (SMTP) ---
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your@gmail.com
SMTP_PASSWORD=your_app_password
MANAGER_EMAIL=manager@company.com

# --- Dashboard ---
DASHBOARD_BASE_URL=http://localhost:7000
```

---

## 🚀 Quick Start

### 1. Start Infrastructure
```bash
docker-compose up -d
```
Starts PostgreSQL (port `5433`) + Redis (port `6379`) with persistent volumes and health checks.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize Database
```bash
python database/init_db.py
```

### 4. Ingest RAG Documents
```bash
python rag/ingest.py
```
Chunks and embeds all PDFs/contracts in `data/` into pgvector.

### 5. Start the API Server
```bash
uvicorn api.main:app --host 0.0.0.0 --port 7000 --reload
```

### 6. Start the Voice Agent
```bash
python voice/livekit_agent.py dev
```

---

## 📡 API Reference

### Core
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/status` | Health check |
| `GET` | `/api/inventory` | All inventory with threshold flags |
| `GET` | `/api/orders` | Full PO history |
| `GET` | `/api/db-analytics` | Financial analytics & counts |
| `POST` | `/api/chat` | Text-based multi-agent query |

### Purchase Orders
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/po/{po_id}` | Fetch PO details (PostgreSQL) |
| `GET` | `/po-detail/{po_id}` | Manager dashboard HTML view |
| `POST` | `/api/po/{po_id}/approve` | Direct approve via REST |
| `POST` | `/api/po/{po_id}/reject` | Direct reject via REST |

### Slack & Reminders
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/slack/actions` | Slack interactive webhook (signature verified) |
| `POST` | `/api/reminders/process` | Trigger reminder/escalation sweep |

### Voice
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/voice/agent/start` | Start LiveKit voice agent session |

---

## 🧪 Testing

```bash
# Test PO approval workflow (auto-approval, pending, duplicate guard)
python tests/test_po_approval_workflow.py

# Test 4-stage reminder & escalation system (with time simulation)
python tests/test_reminder_escalation.py

# Test database connectivity
python tests/test_db_conn.py

# Verify full agent + RAG flow
python tests/verify_flow.py
```

---

## 📂 Project Structure

```
├── agents/               # LangGraph multi-agent nodes
│   ├── supervisor.py
│   ├── inventory_agent.py
│   ├── supplier_agent.py
│   ├── risk_agent.py
│   └── procurement_agent.py
├── api/
│   └── main.py           # FastAPI application & all endpoints
├── database/
│   ├── connection.py
│   ├── schema.sql
│   └── init_db.py
├── rag/
│   ├── ingest.py          # Chunking & pgvector embedding pipeline
│   └── retriever.py       # Semantic similarity retrieval
├── services/
│   ├── slack_service.py   # Slack Block Kit cards & signature verification
│   ├── email_service.py   # SMTP HTML email notifications
│   ├── redis_service.py   # Transient caching layer
│   └── reminder_service.py # 4-stage PO reminder & escalation engine
├── tests/                 # Integrated test and verification suite
│   ├── test_po_approval_workflow.py
│   ├── test_reminder_escalation.py
│   ├── test_db_conn.py
│   ├── test_db_rows.py
│   ├── test_query.py
│   ├── verify_flow.py
│   ├── verify_pipeline.py
│   ├── verify_rag.py
│   └── voice_terminal_test.py
├── voice/
│   ├── livekit_agent.py   # LiveKit WebRTC production agent worker
│   ├── deepgram_stt.py    # Deepgram STT integration
│   ├── elevenlabs_tts.py  # ElevenLabs TTS integration
│   └── pipeline.py        # End-to-end voice pipeline
├── data/                  # Supplier contracts, PDFs for ingestion
├── docker-compose.yml     # PostgreSQL + Redis infrastructure
├── Dockerfile             # Multi-stage container build for FastAPI
├── requirements.txt
└── .env.example
```
