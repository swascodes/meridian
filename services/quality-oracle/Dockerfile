FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY packages/shared /app/packages/shared
RUN pip install --no-cache-dir /app/packages/shared

COPY services/quality-oracle/pyproject.toml /app/services/quality-oracle/
RUN pip install --no-cache-dir fastapi uvicorn[standard]

COPY services/quality-oracle /app/services/quality-oracle

WORKDIR /app/services/quality-oracle

EXPOSE 8003

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8003"]
