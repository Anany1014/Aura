# 🚀Aura

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-green?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-blue?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![pgvector](https://img.shields.io/badge/pgvector-Supported-cyan?style=flat-square)](https://github.com/pgvector/pgvector)
[![Cognee Gated](https://img.shields.io/badge/Cognee-Metadata_Gated_50MB-purple?style=flat-square)](https://github.com/cognee-io/cognee)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)

An automated, graph-based startup discovery engine designed to force **"semantic collisions"** across disparate domains to generate novel, non-obvious business opportunities. 

Unlike basic probabilistic LLMs that regress to derivative concepts, the Innovation Engine maps academic papers, patents, repositories, and startup profiles into a PostgreSQL semantic network, executes graph traversal to locate highly distant but structurally connected nodes, and synthesizes lateral ideas.

---

## 🏗️ 3-Layer Architecture & Execution Pattern

Following deterministic execution patterns, the project separates constraints to ensure ultimate reliability:

```mermaid
flowchart TD
    subgraph Layer 1: Directives ["Layer 1: Directives"]
        direction TB
        sop[SOPs & Markdown Guidelines]
    end

    subgraph Layer 2: Orchestration ["Layer 2: Orchestration"]
        direction TB
        api[FastAPI Routing & Web Services]
        db[(PostgreSQL + pgvector)]
        cognee[Cognee Memory Adapter]
        traversal[CTE Traversal Engine]
        synthesis[Claude Synthesis & Critic]
    end

    subgraph Layer 3: Execution ["Layer 3: Execution"]
        direction TB
        ingest_cli[ingest.py]
        traverse_cli[traverse.py]
        eval_cli[evaluate.py]
        cron[Cron Utilities]
    end

    sop --> api
    api --> traversal --> db
    api --> synthesis --> db
    api --> cognee
    ingest_cli -.-> db
    traverse_cli -.-> db
    eval_cli -.-> db
```

1. **Directives Layer (`directives/`)**
   - Natural language SOPs (Standard Operating Procedures) in Markdown defining pipeline steps, constraints, and success rubrics.
2. **Orchestration Layer (`app/`)**
   - Clean, asynchronous FastAPI wrappers routing requests, managing services, and coordinating fallback mechanisms.
3. **Execution Layer (`execution/`)**
   - Isolated, deterministic scripts (`ingest.py`, `traverse.py`, `synthesize.py`, `evaluate.py`) running cron jobs and standalone utilities.

---

## 🛠️ Tech Stack & Constraints

- **Framework:** FastAPI (Python 3.12+)
- **Database:** PostgreSQL with `pgvector` extension (utilizing HNSW cosine distance indices)
- **Primary LLM APIs:** 
  - OpenAI (`text-embedding-3-small` for semantic node embeddings)
  - Anthropic (`claude-3-5-sonnet-20241022` for Idea Synthesis & Novelty Critic evaluation)
- **Metadata Memory:** Cognee-gated local JSON ledger
- **Guaranteed Operational Cost:** Custom limits designed for a $<50/month boundary, featuring a strict **50MB ceiling** on Cognee operations.

---

## 📦 Project Layout

```text
├── app/
│   ├── api/
│   │   └── router.py             # FastAPI API Endpoints (Ingest, Ingest File, Traverse, Discover, Status)
│   ├── core/
│   │   ├── config.py             # Settings config using Pydantic Settings
│   │   ├── database.py           # Async SQLAlchemy connection and bootstrapping
│   │   └── models.py             # Declarative models (Node, Edge, Idea) with pgvector indexes
│   ├── ingestion/
│   │   └── service.py            # Async ingestion (embeds text and auto-wires nearest edges)
│   ├── memory/
│   │   └── cognee_adapter.py     # Budget-gated Cognee wrapper (50MB ceiling, field blocklist)
│   ├── synthesis/
│   │   └── service.py            # Async Idea Generation (Claude) and Novelty Grading
│   ├── traversal/
│   │   ├── engine.py             # Greedy Graph Walk Service
│   │   └── queries.py            # Postgres Recursive CTE novelty search query
│   └── main.py                   # Server lifespan and startup bootstrapping entrypoint
│
├── directives/                   # SOP templates for pipeline stages
├── execution/                    # Layer 3 utility scripts and database schemas
├── requirements.txt              # Project dependencies
└── README.md
```

---

## 🚀 API Endpoint Reference

| Endpoint | Method | Payload | Functionality |
|---|---|---|---|
| `GET /` | `GET` | *None* | Healthcheck & Status inspection. |
| `POST /api/ingest` | `POST` | `IngestRequest` | Inserts a new node, generates its vector embedding, and auto-wires relation edges. |
| `POST /api/ingest/file` | `POST` | `multipart/form-data` | Parses uploaded documents (PDF, DOCX, TXT, MD) or raw text, indexes them in pgvector, and logs metadata to Cognee. |
| `POST /api/traverse` | `POST` | `TraverseRequest` | Runs Postgres CTE recursive query to compute optimized novelty paths. |
| `POST /api/discover` | `POST` | `DiscoverRequest` | Runs full discovery: Traversal $\rightarrow$ Synthesis $\rightarrow$ Novelty Critic. |
| `GET /api/ideas` | `GET` | *Query Parameters* | Lists previously generated ideas passing the novelty threshold. |
| `GET /api/memory/status` | `GET` | *None* | Queries the memory adapter ledger to monitor used storage and headroom. |

### Payload Examples

#### `POST /api/ingest`
**Request Payload:**
```json
{
  "title": "Quantum Cryptography Keys",
  "domain": "cybersecurity",
  "type": "patent",
  "summary": "Multi-dimensional key distribution utilizing quantum polarization matrices.",
  "content": "Full text details regarding quantum entanglement distribution networks..."
}
```

#### `POST /api/traverse`
**Request Payload:**
```json
{
  "seed_id": "8f8b898c-8db8-4034-9382-7773db872a08",
  "max_hops": 3,
  "domain_penalty": 0.3
}
```

#### `POST /api/discover`
**Request Payload:**
```json
{
  "seed_id": "8f8b898c-8db8-4034-9382-7773db872a08",
  "max_hops": 3,
  "domain_penalty": 0.3
}
```
**Response (Winning Idea):**
```json
{
  "verdict": "PASS",
  "score": 8.5,
  "evaluation": {
    "cross_domain_synthesis": 8.8,
    "market_gap": 8.2,
    "low_budget_feasibility": 8.5
  },
  "idea": {
    "name": "SyntheKey Cryptography",
    "problem_statement": "Distributing encryption keys securely over insecure local meshes...",
    "insight_from_path": "Combining quantum key schedules with edge-meshed graphs...",
    "solution": "A decentralized quantum key synthesis routing agent...",
    "mvp_architecture": "FastAPI service deploying lightweight Python encrypters...",
    "risks": "Prone to high latency overhead on small-tier nodes"
  },
  "database_idea_id": "6a9e889b-9c98-4c34-bc2c-1234db87ea01",
  "cognee_record_id": null
}
```

### Robust Offline Fallback (`SIMULATION_MODE`)
If the PostgreSQL database is unavailable during boot, the backend automatically logs a warning and enters a **Simulation Fallback Mode** (can also be forced via `SIMULATION_MODE=True`). Ingestion, graph CTE walks, and data listings bypass database transactions, returning structured mock datasets so API and frontend clients can continue development offline.

---

## 💻 Setup & Run

### 1. Configure Environment
Create a `.env` file in the root directory (based on `.env.example`):
```bash
# Database Setup (pgvector enabled)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/innovation_engine

# AI Keys
OPENAI_API_KEY=your-openai-api-key
EMBEDDING_MODEL=text-embedding-3-small

ANTHROPIC_API_KEY=your-anthropic-api-key
SYNTHESIS_MODEL=claude-3-5-sonnet-20241022

# Memory Boundaries (Cognee)
COGNEE_METADATA_DIR=.tmp/cognee_meta
COGNEE_MAX_MEMORY_MB=50

# Simulation / Fallback Development
SIMULATION_MODE=False
```

### 2. Start Application
Launch the dev server using the virtual environment:
```bash
# Windows
.venv\Scripts\activate
uvicorn app.main:app --reload

# Linux/macOS
source .venv/bin/activate
uvicorn app.main:app --reload
```
Once booted, access the OpenAPI interactive documentation at `http://localhost:8000/docs`.

---

## 📜 License
Distributed under the MIT License. See `LICENSE` for more information.
