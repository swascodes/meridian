FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY packages/shared /app/packages/shared
RUN pip install --no-cache-dir /app/packages/shared

COPY services/route-optimizer/pyproject.toml /app/services/route-optimizer/
RUN pip install --no-cache-dir fastapi uvicorn[standard] httpx

COPY services/route-optimizer /app/services/route-optimizer

WORKDIR /app/services/route-optimizer

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8002"]
