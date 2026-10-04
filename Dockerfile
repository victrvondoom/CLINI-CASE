# Single-image build for Render (or any Docker host): React UI + FastAPI API on one origin.
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# No VITE_API_BASE: the UI calls /api/* on its own origin.
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 FRONTEND_DIST_DIR=/app/web
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
        tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml /app/
RUN python -m pip install --upgrade pip && pip install -e .
COPY backend/app /app/app
COPY backend/db /app/db
COPY backend/data /app/data
COPY --from=web /web/dist /app/web
RUN useradd --system --uid 10001 --home-dir /app clincase \
    && mkdir -p /app/data && chown -R clincase:clincase /app
USER 10001
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
