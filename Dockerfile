# ── ViewForge — Production Dockerfile ────────────────────────────────────────
# Single image: builds React frontend, installs Python deps + Playwright,
# then serves everything through FastAPI on $PORT (default 8000).

FROM python:3.11-slim

# ── System deps ───────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Playwright browsers ───────────────────────────────────────────────────────
RUN playwright install chromium && playwright install-deps chromium

# ── Frontend build ────────────────────────────────────────────────────────────
COPY frontend/package*.json frontend/
RUN cd frontend && npm ci --silent

COPY frontend/ frontend/
RUN cd frontend && npm run build

# ── Backend ───────────────────────────────────────────────────────────────────
COPY backend/ backend/

# ── Runtime environment ───────────────────────────────────────────────────────
ENV PORT=8000
ENV HOST=0.0.0.0
ENV HEADLESS=true
ENV PROFILES_DIR=/app/profiles

RUN mkdir -p /app/profiles

EXPOSE 8000

CMD ["sh", "-c", "cd backend && python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
