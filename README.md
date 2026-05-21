# ConversalQ — Enterprise AI Call Center Assistant

Production-grade multi-agent AI system for automating call center operations.

## Quick Start

```bash
# Clone and navigate
cd ConversalQ

# Copy environment file
cp .env.example .env
# Edit .env with your OpenAI API key

# Start with Docker Compose
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up --build

# Or run locally
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
# Start server (Windows — uses venv automatically)
powershell -ExecutionPolicy RemoteSigned -File start_server.ps1
Or,
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 (In Powershell)
Or, 
C:\GitProjects\ConversalQ\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir C:\GitProjects\ConversalQ\backend
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- Health Check: http://localhost:8000/api/v1/health

## Sample API Requests

### Chat Completion
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need help with my billing issue",
    "conversation_id": null
  }'
```

### Streaming Chat
```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "message": "What is your refund policy?",
    "conversation_id": null
  }'
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full system design.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, SQLAlchemy |
| AI Orchestration | LangGraph, OpenAI |
| Database | PostgreSQL, Redis, ChromaDB |
| Frontend | React, TailwindCSS, ShadCN |
| Voice | Twilio, Deepgram, ElevenLabs |
| Observability | OpenTelemetry, Prometheus, Grafana |
| Infrastructure | Docker, Kubernetes, GitHub Actions |

## Development Phases

- [x] Phase 1: Foundation — FastAPI + OpenAI + Streaming
- [x] Phase 2: RAG + Vector Database
- [x] Phase 3: Multi-Agent Orchestration (LangGraph)
- [ ] Phase 4: Memory + Session Handling
- [ ] Phase 5: Voice AI Integration
- [ ] Phase 6: Observability + Analytics
- [ ] Phase 7: Enterprise Security + RBAC
- [ ] Phase 8: Cloud Deployment + Scaling

## License

Proprietary — All rights reserved.
