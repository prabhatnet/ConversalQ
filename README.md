---
title: ConversalQ
emoji: 📞
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# ConversalQ — Enterprise AI Call Center Assistant

Production-grade multi-agent AI system for automating call center operations.

## Quick Start

### Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.12+ |
| Node.js | 18+ |
| npm | 9+ |
| PostgreSQL | 15+ |
| Redis | 7+ |

### Backend

```powershell
# Clone and navigate
cd C:\GitProjects\ConversalQ

# Copy environment file and add your OpenAI API key
cp .env.example .env

# Activate the backend virtual environment (IMPORTANT: use backend\.venv, not the root .venv)
& C:\GitProjects\ConversalQ\backend\.venv\Scripts\Activate.ps1

# Install dependencies (first time only)
pip install -r backend\requirements.txt

# Start the API server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir C:\GitProjects\ConversalQ\backend
```

### Frontend (React UI)

```powershell
# Navigate to the frontend folder
cd C:\GitProjects\ConversalQ\frontend

# Install Node dependencies (first time only)
npm install

# Start the dev server (proxies /api requests to the backend automatically)
npm run dev
```

The UI will be available at **http://localhost:5173**.

> The Vite dev server proxies all `/api/*` requests to the backend at `http://localhost:8000`, so both services must be running simultaneously.

### Build for Production

```powershell
cd C:\GitProjects\ConversalQ\frontend
npm run build
# Output is in frontend/dist/ — serve with any static file host or Nginx
```

## Running Services

| Service | URL | Description |
|---|---|---|
| React UI | http://localhost:5173 | Transcript Replay · Live Chat · Audio Upload tabs |
| Backend API | http://localhost:8000 | FastAPI REST server |
| Swagger UI | http://localhost:8000/docs | Interactive API explorer |
| Health Check | http://localhost:8000/api/v1/health | Liveness probe |

## API Endpoints

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat` | Send a message, receive a complete AI response |
| POST | `/api/v1/chat/stream` | Send a message, receive a streaming SSE response |
| POST | `/api/v1/chat/replay` | Replay a full transcript JSON through the agent graph |
| GET | `/api/v1/chat/{id}/history` | Retrieve full message history for a conversation |
| GET | `/api/v1/chat/{id}/summary` | Retrieve the LLM-generated memory summary |
| POST | `/api/v1/chat/{id}/qa-score` | Run the QA Scoring Agent on a completed conversation |
| PATCH | `/api/v1/chat/{id}/status` | Manually update conversation status |

### Knowledge Base
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/knowledge/ingest` | Ingest a document into the vector store |
| POST | `/api/v1/knowledge/search` | Semantic search the knowledge base |
| GET | `/api/v1/knowledge/stats` | Collection statistics |
| GET | `/api/v1/knowledge/documents` | List ingested documents |
| DELETE | `/api/v1/knowledge/documents/{filename}` | Delete a document |

### Agents
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/agents` | List registered agents and their capabilities |
| GET | `/api/v1/agents/graph` | Retrieve the agent graph topology |

### Voice
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/voice/inbound` | Twilio inbound call webhook — returns TwiML greeting |
| POST | `/api/v1/voice/gather` | Twilio Gather webhook — processes speech, returns TwiML reply |
| POST | `/api/v1/voice/status` | Twilio status callback — syncs call lifecycle |
| POST | `/api/v1/voice/upload` | Upload an audio file (WAV/MP3/FLAC/OGG…) — returns Deepgram transcript |
| GET | `/api/v1/voice/sessions` | List active call sessions (`?active_only=false` for all) |
| GET | `/api/v1/voice/sessions/{call_sid}` | Get single call session by CallSid |
| WS | `/api/v1/voice/stream/{call_sid}` | Twilio Media Stream — live Deepgram STT transcription |

## Sample API Requests

> **PowerShell note:** Use single quotes for the `-d` body — no backslash escaping needed.

### Chat Completion
```powershell
curl.exe -X POST http://localhost:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d '{"message": "I need help with my billing issue"}'
```

### Continue a Conversation
```powershell
# Use the conversation_id returned from the first call
curl.exe -X POST http://localhost:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d '{"message": "Can I get a refund?", "conversation_id": "<id>"}'
```

### Streaming Chat
```powershell
curl.exe -X POST http://localhost:8000/api/v1/chat/stream `
  -H "Content-Type: application/json" `
  -H "Accept: text/event-stream" `
  -d '{"message": "What is your refund policy?"}'
```

### Conversation History
```powershell
curl.exe http://localhost:8000/api/v1/chat/<conversation_id>/history
```

### Conversation Summary
```powershell
curl.exe http://localhost:8000/api/v1/chat/<conversation_id>/summary
```

### Resolve a Conversation
```powershell
curl.exe -X PATCH http://localhost:8000/api/v1/chat/<conversation_id>/status `
  -H "Content-Type: application/json" `
  -d '{"status": "resolved"}'
```

### Replay a Transcript (Batch)
```powershell
# Submit a full transcript JSON to replay all customer turns through the agent graph
curl.exe -X POST http://localhost:8000/api/v1/chat/replay `
  -H "Content-Type: application/json" `
  -d '{
    "call_id": "CALL_001",
    "transcript": [
      {"speaker": "agent",    "text": "Hi, how can I help?", "timestamp_offset": 0},
      {"speaker": "customer", "text": "I was charged twice this month.", "timestamp_offset": 5},
      {"speaker": "customer", "text": "Both charges are $49.99 on May 3rd.", "timestamp_offset": 18}
    ]
  }'
```

> Tip: drop any file from `data/sample_transcripts/` into the React UI at http://localhost:5173 for a visual replay.

### Simulate Twilio Inbound Call
```powershell
# Simulates the webhook Twilio sends when a call arrives
curl.exe -X POST http://localhost:8000/api/v1/voice/inbound `
  -H "Content-Type: application/x-www-form-urlencoded" `
  -d "CallSid=CA1234567890abcdef&From=%2B15551112222&To=%2B15559998888&CallStatus=ringing"
```

### Simulate Twilio Gather (Caller Speaks)
```powershell
# Simulates Twilio posting back the transcribed speech
curl.exe -X POST http://localhost:8000/api/v1/voice/gather `
  -H "Content-Type: application/x-www-form-urlencoded" `
  -d "CallSid=CA1234567890abcdef&SpeechResult=I+have+a+billing+issue&Confidence=0.92"
```

### List Active Voice Calls
```powershell
curl.exe http://localhost:8000/api/v1/voice/sessions
```

### Get Call Session Details
```powershell
curl.exe http://localhost:8000/api/v1/voice/sessions/CA1234567890abcdef
```

### QA Score a Conversation
```powershell
curl.exe -X POST http://localhost:8000/api/v1/chat/<conversation_id>/qa-score `
  -H "Content-Type: application/json" `
  -d '{"notes": null}'
```

Response includes four scored dimensions (empathy, tone, resolution, professionalism), LLM reasoning per dimension, overall score 0–100, and latency.

### Transcribe an Audio File
```powershell
# Requires DEEPGRAM_API_KEY to be set in backend/.env
curl.exe -X POST http://localhost:8000/api/v1/voice/upload `
  -F "file=@data/sample_audio/sample_call_billing.wav"
```

Sample audio files are in `data/sample_audio/`. Accepted formats: WAV, MP3, MP4, M4A, OGG, WEBM, FLAC, AAC. Max 25 MB.

> Tip: use the **Audio Upload** tab in the React UI at http://localhost:5173 for a drag-and-drop interface.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full system design.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 |
| AI Orchestration | LangGraph 1.2, LangChain OpenAI 1.2 |
| LLM | OpenAI GPT-4o |
| QA Scoring | GPT-4o function calling, 4-dimension rubric, Pydantic-enforced JSON schema |
| Vector Store | ChromaDB (HTTP client) |
| Database | PostgreSQL, Redis, ChromaDB |
| Embeddings | OpenAI text-embedding-3-small |
| Logging | structlog |
| Tracing | LangSmith 0.3 (opt-in via `LANGSMITH_TRACING=true`) |
| MCP | `mcp.yaml` — 7 tools, 2 resources, 2 prompts over HTTP transport |
| Frontend | React 19, Vite 8, Tailwind CSS 4, lucide-react |
| Voice | Twilio 9.4 (TwiML + webhook validation), Deepgram SDK 3.7 (live STT + file upload), OpenAI TTS |
| Guardrails | Rate limiting (sliding window, per-IP), prompt injection detection (heuristic), OpenAI content moderation (opt-in) |
| Observability | OpenTelemetry, Prometheus, Grafana |
| Infrastructure | Docker, Kubernetes, GitHub Actions |

## Development Phases

- [x] Phase 1: Foundation — FastAPI + OpenAI + Streaming
- [x] Phase 2: RAG + Vector Database (ChromaDB)
- [x] Phase 3: Multi-Agent Orchestration (LangGraph)
- [x] Phase 4: Memory + Session Handling
- [x] Phase 5: Voice AI Integration (Twilio + Deepgram + OpenAI TTS)
- [x] Phase 5+: QA Scoring Agent (GPT-4o function calling, 4-dimension rubric)
- [x] Phase 5+: Audio File Upload (Deepgram pre-recorded API, drag-and-drop UI)
- [x] Phase 5+: LangSmith Tracing (opt-in, zero-instrumentation)
- [x] Phase 5+: MCP Server Declaration (mcp.yaml, 7 tools)
- [x] Phase 6+: Guardrails — rate limiting, prompt injection detection, content moderation
- [ ] Phase 6: Observability + Analytics
- [ ] Phase 7: Enterprise Security + RBAC
- [ ] Phase 8: Cloud Deployment + Scaling

## License

Proprietary — All rights reserved.
