# Meridian

AI-powered routing intelligence network for Stellar.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Developer API (:8000)                    │
├──────────┬──────────┬──────────┬──────────┬────────────────────┤
│  Graph   │  Route   │ Quality  │Predictive│    Ingestion       │
│  Engine  │Optimizer │  Oracle  │  Engine  │    Pipeline        │
│  :8001   │  :8002   │  :8003   │  :8004   │    :8005           │
├──────────┴──────────┴──────────┴──────────┴────────────────────┤
│              PostgreSQL + TimescaleDB │ Redis                   │
├─────────────────────────────────────────────────────────────────┤
│         Stellar Horizon │ Soroban RPC │ Routing Registry        │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Copy environment config
cp .env.example .env

# 2. Start all services
make dev

# 3. Start frontend (separate terminal)
cd frontend && npm run dev

# 4. Check health
make health
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| API Gateway | 8000 | Public REST API |
| Graph Engine | 8001 | Asset graph (NetworkX) |
| Route Optimizer | 8002 | Multi-objective optimization |
| Quality Oracle | 8003 | Route quality scoring |
| Predictive Engine | 8004 | ML prediction (Phase 1 stub) |
| Ingestion | 8005 | Stellar data pipeline |
| Frontend | 3000 | Next.js dashboard |

## Development

```bash
make test          # Run all tests
make lint          # Lint all services
make fmt           # Format code
make contract-build # Build Soroban contract
make contract-test  # Test Soroban contract
```

## API

Full OpenAPI docs at `http://localhost:8000/docs`.

Key endpoints:
- `GET /v1/routes/{source}/{dest}` — Find optimal routes
- `POST /v1/routes/simulate` — Simulate execution
- `GET /v1/graph/stats` — Graph topology
- `GET /v1/quality/{route_hash}` — Route quality score
- `POST /v1/registry/publish` — Publish to Soroban

## Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy, NetworkX
- **Database**: PostgreSQL + TimescaleDB, Redis
- **Blockchain**: Stellar SDK, Soroban (Rust)
- **Frontend**: Next.js 15, TypeScript, Tailwind CSS
- **Infrastructure**: Docker Compose

## License

BUSL-1.1
