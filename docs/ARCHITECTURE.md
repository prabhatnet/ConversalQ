# ConversalQ — Enterprise AI Call Center Assistant

## Overall Architecture Plan

---

## 1. System Overview

ConversalQ is an enterprise-grade AI Call Center Assistant that orchestrates multiple specialized AI agents to automate customer support operations. The system uses multi-agent orchestration (LangGraph), RAG pipelines, conversational memory, voice AI, sentiment analysis, and intelligent escalation workflows.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                 │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ React UI │  │ Voice Client │  │ Admin UI │  │ Analytics UI  │  │
│  └─────┬────┘  └──────┬───────┘  └─────┬────┘  └───────┬───────┘  │
└────────┼───────────────┼────────────────┼───────────────┼──────────┘
         │               │                │               │
┌────────▼───────────────▼────────────────▼───────────────▼──────────┐
│                      API GATEWAY LAYER                              │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  FastAPI Application (ASGI)                                   │  │
│  │  • Authentication / JWT                                       │  │
│  │  • Rate Limiting                                              │  │
│  │  • Request Routing                                            │  │
│  │  • CORS / Security Headers                                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────┬───────────────┬────────────────┬───────────────┬──────────┘
         │               │                │               │
┌────────▼───────────────▼────────────────▼───────────────▼──────────┐
│                     SERVICE LAYER                                   │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌─────────────┐  │
│  │ Chat     │  │ Voice        │  │ Analytics │  │ Admin       │  │
│  │ Service  │  │ Service      │  │ Service   │  │ Service     │  │
│  └─────┬────┘  └──────┬───────┘  └─────┬─────┘  └──────┬──────┘  │
└────────┼───────────────┼────────────────┼───────────────┼──────────┘
         │               │                │               │
┌────────▼───────────────▼────────────────▼───────────────▼──────────┐
│                  ORCHESTRATION LAYER (LangGraph)                    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Agent Supervisor / Router                                  │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │    │
│  │  │ Intent   │ │ Customer │ │Knowledge │ │ Billing      │  │    │
│  │  │ Detector │ │ Verifier │ │Base Agent│ │ Agent        │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │    │
│  │  │Tech      │ │Sentiment │ │Escalation│ │ Compliance   │  │    │
│  │  │Support   │ │Analyzer  │ │Agent     │ │ Monitor      │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │    │
│  │  ┌──────────┐ ┌──────────────┐                              │    │
│  │  │Summarizer│ │Recommendation│                              │    │
│  │  │Agent     │ │Agent         │                              │    │
│  │  └──────────┘ └──────────────┘                              │    │
│  └────────────────────────────────────────────────────────────┘    │
└────────┬───────────────┬────────────────┬───────────────┬──────────┘
         │               │                │               │
┌────────▼───────────────▼────────────────▼───────────────▼──────────┐
│                     DATA LAYER                                      │
│  ┌───────────┐  ┌──────────┐  ┌───────────┐  ┌────────────────┐  │
│  │PostgreSQL │  │  Redis   │  │ ChromaDB  │  │ File Storage   │  │
│  │(Primary)  │  │ (Cache/  │  │ (Vector   │  │ (Documents)    │  │
│  │           │  │  Session)│  │  Store)   │  │                │  │
│  └───────────┘  └──────────┘  └───────────┘  └────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
         │               │                │
┌────────▼───────────────▼────────────────▼─────────────────────────┐
│                  OBSERVABILITY LAYER                                │
│  ┌────────────────┐  ┌────────────┐  ┌────────────────────────┐  │
│  │ OpenTelemetry  │  │ Prometheus │  │ Grafana Dashboards     │  │
│  │ (Traces/Logs)  │  │ (Metrics)  │  │ (Visualization)        │  │
│  └────────────────┘  └────────────┘  └────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```

---

## 2. Phase Plan

### Phase 1: Foundation — Basic Chatbot + FastAPI + OpenAI (Current)
**Objectives:**
- Set up project scaffolding with clean architecture
- Implement FastAPI with async endpoints
- Integrate OpenAI for basic chat completion
- Add streaming response support (SSE)
- Set up Docker development environment
- Implement basic conversation storage (PostgreSQL)
- Structured logging foundation

### Phase 2: RAG Integration + Vector Database
**Objectives:**
- Document ingestion pipeline (PDF, TXT, Markdown)
- Embedding generation with OpenAI embeddings
- ChromaDB vector store integration
- Chunking strategies (recursive, semantic)
- Semantic retrieval with similarity search
- Hybrid search (keyword + semantic)
- Citation-aware response generation
- Knowledge base management API

### Phase 3: Multi-Agent Orchestration
**Status: Complete**

**Implemented:**
- LangGraph `StateGraph` with `AgentState` TypedDict shared across all nodes
- Router node — LLM-based intent classification (billing / technical / account / general / escalation) with confidence scoring
- 5 specialist agent nodes built via a factory function (`_make_specialist_node`)
- Conditional edges: router → specialist based on intent; all specialists → END
- `get_compiled_graph()` cached with `@lru_cache` for process-lifetime reuse
- `AgentOrchestrationService` — orchestrates RAG prefetch + graph invocation + response extraction
- `ChatOpenAI` used for all LLM calls; `AsyncOpenAI` for embeddings
- SSE streaming via `astream_events(version="v2")`
- `AgentResponse` dataclass carries: content, intent, active_agent, confidence, rag_sources, should_escalate, escalation_reason, latency_ms
- `ChatResponse` schema enriched with agent metadata fields

### Phase 4: Memory + Session Handling
**Status: Complete**

**Implemented:**
- `ConversationMemoryService` — sliding-window context with LLM-powered rolling summarization
  - Configurable via settings: `MEMORY_WINDOW_SIZE` (default 6), `MEMORY_SUMMARIZE_THRESHOLD` (10), `MEMORY_SUMMARIZE_STEP` (4)
  - Short conversations (≤ threshold): all messages passed verbatim
  - Long conversations: last N messages verbatim + LLM summary of older turns
  - Summary stored on `conversation.summary`; re-generated every `SUMMARIZE_STEP` new messages
  - Summarization watermark tracked in `conversation.metadata_["summarized_through"]`
- `conversation_summary` field added to `AgentState` — injected into router prompt and all specialist system prompts
- Conversation status lifecycle: `active → escalated` auto-transition when `should_escalate=True`
- Manual status management via `PATCH /api/v1/chat/{id}/status` (active / resolved / escalated / closed)
- `update_summary()` + `update_status()` added to both `InMemoryConversationRepository` and `ConversationRepository`
- New endpoints:
  - `GET /api/v1/chat/{id}/history` — full chronological message list + status
  - `GET /api/v1/chat/{id}/summary` — LLM memory summary + turn count
  - `PATCH /api/v1/chat/{id}/status` — manual lifecycle transition

### Phase 5: Voice AI Integration
**Objectives:**
- Twilio Voice webhook handlers
- Real-time speech-to-text (Deepgram)
- Text-to-speech responses (ElevenLabs/OpenAI TTS)
- Call session lifecycle management
- Voice sentiment analysis
- Streaming audio pipeline
- DTMF handling

### Phase 6: Observability + Analytics
**Objectives:**
- OpenTelemetry instrumentation
- Prometheus metrics collection
- Grafana dashboard setup
- Structured logging with correlation IDs
- Agent performance analytics
- Latency monitoring per agent
- Error tracking and alerting
- Conversation analytics dashboard

### Phase 7: Enterprise Security + RBAC
**Objectives:**
- JWT authentication with refresh tokens
- Role-based access control (Admin, Supervisor, Agent, API)
- API key management
- PII masking in logs and storage
- Audit trail logging
- Rate limiting per role/endpoint
- Secrets management (Vault-ready)
- Input sanitization and validation

### Phase 8: Cloud Deployment + Scaling
**Objectives:**
- Kubernetes manifests (Helm charts)
- CI/CD with GitHub Actions
- Multi-environment configuration
- Auto-scaling policies
- Health check endpoints
- Blue-green deployment support
- Cloud provider deployment guides
- Load testing and benchmarking

---

## 3. Folder Structure (Full Project)

```
ConversalQ/
├── docs/                           # Documentation
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── DEPLOYMENT.md
│   └── AGENTS.md
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application entry point
│   │   ├── config.py               # Application configuration
│   │   ├── dependencies.py         # Dependency injection
│   │   │
│   │   ├── api/                    # API layer (routers)
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py       # V1 API router aggregator
│   │   │   │   ├── chat.py         # Chat endpoints
│   │   │   │   ├── voice.py        # Voice endpoints
│   │   │   │   ├── knowledge.py    # Knowledge base endpoints
│   │   │   │   ├── analytics.py    # Analytics endpoints
│   │   │   │   ├── admin.py        # Admin endpoints
│   │   │   │   └── health.py       # Health check endpoints
│   │   │   └── middleware/
│   │   │       ├── __init__.py
│   │   │       ├── cors.py
│   │   │       ├── rate_limiter.py
│   │   │       ├── request_id.py
│   │   │       └── error_handler.py
│   │   │
│   │   ├── core/                   # Core business logic
│   │   │   ├── __init__.py
│   │   │   ├── exceptions.py       # Custom exceptions
│   │   │   ├── security.py         # Auth utilities
│   │   │   └── events.py           # Application lifecycle events
│   │   │
│   │   ├── services/               # Service layer
│   │   │   ├── __init__.py
│   │   │   ├── chat_service.py      # Phase 1-4: chat orchestration, memory, status
│   │   │   ├── memory_service.py    # Phase 4: sliding-window + LLM summarization
│   │   │   ├── knowledge_service.py # Phase 2: RAG document management
│   │   │   └── llm_service.py      # Phase 1: LLM abstraction (legacy)
│   │   │
│   │   ├── agents/                 # AI Agent definitions (Phase 3)
│   │   │   ├── __init__.py
│   │   │   ├── graph.py            # LangGraph StateGraph compilation
│   │   │   ├── state.py            # AgentState TypedDict
│   │   │   ├── router.py           # Intent classification node
│   │   │   ├── specialists.py      # 5 specialist agent nodes
│   │   │   └── orchestration.py    # AgentOrchestrationService
│   │   │
│   │   ├── models/                 # Database models (SQLAlchemy)
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── conversation.py
│   │   │   ├── message.py
│   │   │   ├── user.py
│   │   │   ├── customer.py
│   │   │   └── audit_log.py
│   │   │
│   │   ├── schemas/                # Pydantic schemas
│   │   │   ├── __init__.py
│   │   │   ├── chat.py
│   │   │   ├── voice.py
│   │   │   ├── conversation.py
│   │   │   ├── user.py
│   │   │   └── common.py
│   │   │
│   │   ├── repositories/           # Data access layer
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── conversation_repo.py
│   │   │   ├── message_repo.py
│   │   │   └── user_repo.py
│   │   │
│   │   ├── rag/                    # RAG pipeline
│   │   │   ├── __init__.py
│   │   │   ├── ingestion.py
│   │   │   ├── embeddings.py
│   │   │   ├── chunking.py
│   │   │   ├── retriever.py
│   │   │   └── vector_store.py
│   │   │
│   │   ├── voice/                  # Voice AI pipeline
│   │   │   ├── __init__.py
│   │   │   ├── twilio_handler.py
│   │   │   ├── stt.py              # Speech-to-text
│   │   │   ├── tts.py              # Text-to-speech
│   │   │   └── session.py
│   │   │
│   │   ├── observability/          # Monitoring & telemetry
│   │   │   ├── __init__.py
│   │   │   ├── tracing.py
│   │   │   ├── metrics.py
│   │   │   └── logging.py
│   │   │
│   │   └── db/                     # Database utilities
│   │       ├── __init__.py
│   │       ├── session.py          # Async session factory
│   │       └── migrations/         # Alembic migrations
│   │           ├── env.py
│   │           └── versions/
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── unit/
│   │   │   ├── __init__.py
│   │   │   ├── test_chat_service.py
│   │   │   └── test_llm_service.py
│   │   ├── integration/
│   │   │   ├── __init__.py
│   │   │   └── test_chat_api.py
│   │   └── e2e/
│   │       └── __init__.py
│   │
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/                       # React/Next.js (Phase 4+)
│   └── ...
│
├── infra/                          # Infrastructure
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   ├── prometheus/
│   │   └── prometheus.yml
│   ├── grafana/
│   │   └── dashboards/
│   └── k8s/
│       ├── namespace.yml
│       ├── deployment.yml
│       ├── service.yml
│       └── configmap.yml
│
├── scripts/                        # Utility scripts
│   ├── seed_db.py
│   ├── ingest_docs.py
│   └── healthcheck.sh
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
│
├── .env.example
├── .gitignore
├── .dockerignore
├── Makefile
└── README.md
```

---

## 4. Key Architecture Decisions

### 4.1 Clean Architecture / Hexagonal Architecture
- **API Layer** → HTTP concerns only (request parsing, response formatting)
- **Service Layer** → Business logic orchestration
- **Repository Layer** → Data access abstraction
- **Model Layer** → Domain entities
- **Schema Layer** → API contracts (Pydantic)

### 4.2 Dependency Injection
All services injected via FastAPI `Depends()`. No global state. Enables testing with mocks.

### 4.3 Async-First
All I/O-bound operations use `async/await`. SQLAlchemy async sessions, httpx for HTTP calls, async OpenAI client.

### 4.4 LangGraph for Orchestration
Chosen over CrewAI for:
- Explicit state machine control
- Conditional routing between agents
- Better debuggability
- Native tool calling support
- Production-grade error handling

### 4.5 Event-Driven Communication
Internal events for cross-cutting concerns (audit logging, analytics, notifications) without tight coupling.

### 4.6 API Versioning
`/api/v1/` prefix for all endpoints. Allows non-breaking evolution.

---

## 5. Database Schema (Core)

```sql
-- conversations
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    channel VARCHAR(20) NOT NULL DEFAULT 'chat',  -- chat, voice, api
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active, resolved, escalated
    sentiment_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- messages
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- user, assistant, system, agent
    content TEXT NOT NULL,
    agent_name VARCHAR(100),
    confidence_score FLOAT,
    token_count INTEGER,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- audit_logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action VARCHAR(100) NOT NULL,
    actor_id UUID,
    resource_type VARCHAR(100),
    resource_id UUID,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 6. Interview Talking Points (Per Phase)

### Phase 1
- "I designed a clean architecture with clear separation between API, service, and data layers"
- "I implemented async-first patterns with FastAPI and SQLAlchemy for high concurrency"
- "I used SSE streaming for real-time chat responses to reduce perceived latency"
- "I containerized from day one with Docker Compose for reproducible environments"
- "I implemented structured logging with structlog and correlation IDs for request tracing"

### Phase 2
- "I built a full RAG pipeline: PDF/DOCX/TXT ingestion, token-accurate chunking with tiktoken, OpenAI embeddings with SHA-256 in-process cache, and ChromaDB vector store"
- "I used chromadb-client (HTTP-only) to avoid native C++ build-tool dependencies in the dev environment"
- "Citation-aware retrieval formats source references directly into agent context blocks"
- "The knowledge base API is fully CRUD: ingest, search, list, delete, reset"

### Phase 3
- "I replaced the monolithic LLM call with a LangGraph state machine: router node classifies intent, conditional edges route to one of 5 specialist agents"
- "The router uses LLM-based confidence scoring — below 0.45 it auto-escalates rather than guessing"
- "All agents share a single AgentState TypedDict; the add_messages reducer handles message history merging"
- "RAG context is prefetched before graph execution so every specialist sees the same retrieved chunks without redundant embedding calls"
- "The compiled graph is cached with @lru_cache so LangGraph compilation cost is paid once at startup"

### Phase 4
- "I implemented a sliding-window memory system: the last 6 messages are passed verbatim; older turns are compressed into a rolling LLM-generated summary stored on the conversation record"
- "Summarization is lazy and incremental — it only re-runs when the old window has grown by 4+ messages, keeping token costs low"
- "The summary is injected into both the router (for accurate re-routing in long sessions) and specialist agents (for conversational continuity)"
- "Conversation status transitions automatically — active → escalated when the escalation agent fires; agents or operators can also manually resolve/close via PATCH endpoint"

---

## 7. Production Improvements Roadmap
- Circuit breaker pattern for external API calls (OpenAI, Twilio)
- Message queue (RabbitMQ/SQS) for async processing
- Read replicas for PostgreSQL
- CDN for frontend static assets
- WebSocket support for bidirectional real-time communication
- A/B testing framework for agent prompt optimization
- Feature flags for gradual rollout
- Multi-tenancy support
- Data retention policies and GDPR compliance
