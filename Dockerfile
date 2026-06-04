# =============================================================================
# ConversalQ — Hugging Face Spaces Dockerfile
# Multi-stage: React build → Python runtime
# HF Spaces requires port 7860
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build React frontend
# ---------------------------------------------------------------------------
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: Python runtime (serves both API and static SPA)
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Security: non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

# Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application source
COPY backend/app/ ./app/

# Built React SPA — FastAPI serves this via StaticFiles
COPY --from=frontend-builder /app/frontend/dist ./static/

# Ownership
RUN chown -R appuser:appuser /app

USER appuser

# HF Spaces requirement: expose port 7860
EXPOSE 7860

# Single worker — HF Spaces free tier is single-container
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
