FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install shared package first (cacheable layer)
COPY packages/shared /app/packages/shared
RUN pip install --no-cache-dir /app/packages/shared

# Install service dependencies
COPY services/api/pyproject.toml /app/services/api/
RUN pip install --no-cache-dir fastapi uvicorn[standard] httpx

# Copy service code
COPY services/api /app/services/api

WORKDIR /app/services/api

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
