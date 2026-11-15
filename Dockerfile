# ==============================================================================
# PROJECT SUKOON BACKEND — MULTI-ARCH DOCKERFILE (ARM64 & AMD64)
# ==============================================================================
FROM python:3.10-slim-bullseye AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install minimal OS dependencies for compilation and cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt

# Development target
FROM base AS dev
RUN pip install -r requirements-dev.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "sukoon.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production target
FROM base AS prod
COPY . .
# Create non-root user for security
RUN useradd -m -u 1000 sukoon && chown -R sukoon:sukoon /app
USER sukoon
EXPOSE 8000
CMD ["uvicorn", "sukoon.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
