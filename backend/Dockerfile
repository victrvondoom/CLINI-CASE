FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
RUN python -m pip install --upgrade pip && \
    pip install -e .

COPY app /app/app
COPY db  /app/db
# Synthetic Track 7 payloads read by POST /api/v1/interop/demo, plus CardioTwin reference data.
COPY data /app/data

# Run unprivileged: the app only needs to read /app and write under /app/data (policy store).
RUN useradd --system --uid 10001 --home-dir /app clincase \
    && mkdir -p /app/data && chown -R clincase:clincase /app
USER 10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fs http://localhost:8000/api/v1/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
