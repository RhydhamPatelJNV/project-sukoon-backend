# ==============================================================================
# PROJECT SUKOON BACKEND — MODERN DOCKERFILE (RENDER & CLOUD READY)
# ==============================================================================
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir uvicorn[standard] httpx psutil

COPY sukoon/ ./sukoon/

EXPOSE 8000
CMD ["sh", "-c", "uvicorn sukoon.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
