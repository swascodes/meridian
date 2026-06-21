-- Meridian PostgreSQL Initialization
-- Requires TimescaleDB extension

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ─── Assets ───

CREATE TABLE IF NOT EXISTS assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(12) NOT NULL,
    issuer VARCHAR(56),
    asset_type VARCHAR(20) NOT NULL,
    domain VARCHAR(255),
    is_verified BOOLEAN DEFAULT FALSE,
    total_trustlines BIGINT DEFAULT 0,
    total_volume_24h DOUBLE PRECISION DEFAULT 0.0,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB,
    CONSTRAINT uq_asset_code_issuer UNIQUE (code, issuer)
);

CREATE INDEX IF NOT EXISTS ix_asset_code ON assets (code);
CREATE INDEX IF NOT EXISTS ix_asset_volume ON assets (total_volume_24h DESC);

-- ─── Liquidity Pools ───

CREATE TABLE IF NOT EXISTS liquidity_pools (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pool_id VARCHAR(64) UNIQUE NOT NULL,
    asset_a_id UUID NOT NULL REFERENCES assets(id),
    asset_b_id UUID NOT NULL REFERENCES assets(id),
    reserve_a NUMERIC(20, 7) NOT NULL,
    reserve_b NUMERIC(20, 7) NOT NULL,
    total_shares NUMERIC(20, 7) NOT NULL,
    fee_bp INTEGER DEFAULT 30,
    total_trustlines BIGINT DEFAULT 0,
    last_updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_pool_assets ON liquidity_pools (asset_a_id, asset_b_id);

-- ─── Orderbook Snapshots (Hypertable) ───

CREATE TABLE IF NOT EXISTS orderbook_snapshots (
    id UUID DEFAULT uuid_generate_v4(),
    base_asset_id UUID NOT NULL REFERENCES assets(id),
    counter_asset_id UUID NOT NULL REFERENCES assets(id),
    timestamp TIMESTAMPTZ NOT NULL,
    bids JSONB NOT NULL,
    asks JSONB NOT NULL,
    bid_depth NUMERIC(20, 7) NOT NULL,
    ask_depth NUMERIC(20, 7) NOT NULL,
    spread DOUBLE PRECISION NOT NULL,
    mid_price DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (id, timestamp)
);

SELECT create_hypertable('orderbook_snapshots', 'timestamp', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_orderbook_pair_time ON orderbook_snapshots (base_asset_id, counter_asset_id, timestamp DESC);

-- Retention policy: keep 30 days of orderbook snapshots
SELECT add_retention_policy('orderbook_snapshots', INTERVAL '30 days', if_not_exists => TRUE);

-- ─── Trades (Hypertable) ───

CREATE TABLE IF NOT EXISTS trades (
    id UUID DEFAULT uuid_generate_v4(),
    stellar_trade_id VARCHAR(64) UNIQUE NOT NULL,
    base_asset_id UUID NOT NULL REFERENCES assets(id),
    counter_asset_id UUID NOT NULL REFERENCES assets(id),
    base_amount NUMERIC(20, 7) NOT NULL,
    counter_amount NUMERIC(20, 7) NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    base_is_seller BOOLEAN NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    ledger_close_time TIMESTAMPTZ NOT NULL,
    trade_type VARCHAR(20) NOT NULL,
    liquidity_pool_id VARCHAR(64),
    PRIMARY KEY (id, timestamp)
);

SELECT create_hypertable('trades', 'timestamp', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_trade_pair_time ON trades (base_asset_id, counter_asset_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_trade_time ON trades (timestamp DESC);

-- Retention policy: keep 90 days of trade history
SELECT add_retention_policy('trades', INTERVAL '90 days', if_not_exists => TRUE);

-- ─── Routes ───

CREATE TABLE IF NOT EXISTS routes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    route_hash VARCHAR(64) UNIQUE NOT NULL,
    source_asset_id UUID NOT NULL REFERENCES assets(id),
    destination_asset_id UUID NOT NULL REFERENCES assets(id),
    path JSONB NOT NULL,
    hop_count INTEGER NOT NULL,
    estimated_rate DOUBLE PRECISION,
    estimated_slippage DOUBLE PRECISION,
    total_liquidity DOUBLE PRECISION,
    is_active BOOLEAN DEFAULT TRUE,
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    last_validated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS ix_route_pair ON routes (source_asset_id, destination_asset_id);
CREATE INDEX IF NOT EXISTS ix_route_active ON routes (is_active) WHERE is_active = TRUE;

-- ─── Route Executions ───

CREATE TABLE IF NOT EXISTS route_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    route_id UUID NOT NULL REFERENCES routes(id),
    executed_at TIMESTAMPTZ NOT NULL,
    input_amount NUMERIC(20, 7) NOT NULL,
    expected_output NUMERIC(20, 7) NOT NULL,
    actual_output NUMERIC(20, 7),
    slippage DOUBLE PRECISION,
    execution_time_ms INTEGER,
    status VARCHAR(20) NOT NULL,
    stellar_tx_hash VARCHAR(64),
    error_detail TEXT
);

CREATE INDEX IF NOT EXISTS ix_execution_route_time ON route_executions (route_id, executed_at DESC);

-- ─── Route Quality Scores ───

CREATE TABLE IF NOT EXISTS route_quality_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    route_id UUID NOT NULL REFERENCES routes(id),
    scored_at TIMESTAMPTZ DEFAULT NOW(),
    composite_score DOUBLE PRECISION NOT NULL,
    liquidity_score DOUBLE PRECISION NOT NULL,
    reliability_score DOUBLE PRECISION NOT NULL,
    speed_score DOUBLE PRECISION NOT NULL,
    cost_score DOUBLE PRECISION NOT NULL,
    slippage_score DOUBLE PRECISION NOT NULL,
    sample_size INTEGER NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    breakdown JSONB
);

CREATE INDEX IF NOT EXISTS ix_quality_route_time ON route_quality_scores (route_id, scored_at DESC);

-- ─── Registered Routes (Soroban) ───

CREATE TABLE IF NOT EXISTS registered_routes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    route_id UUID NOT NULL REFERENCES routes(id),
    contract_id VARCHAR(56) NOT NULL,
    soroban_tx_hash VARCHAR(64) NOT NULL,
    registered_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated_at TIMESTAMPTZ DEFAULT NOW(),
    on_chain_score DOUBLE PRECISION NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS ix_registered_contract ON registered_routes (contract_id);

-- ─── Ingestion Cursors ───

CREATE TABLE IF NOT EXISTS ingestion_cursors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    stream_name VARCHAR(50) UNIQUE NOT NULL,
    cursor_value VARCHAR(255) NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Continuous Aggregates ───

-- 1-minute OHLCV for trades
CREATE MATERIALIZED VIEW IF NOT EXISTS trades_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', timestamp) AS bucket,
    base_asset_id,
    counter_asset_id,
    first(price, timestamp) AS open,
    max(price) AS high,
    min(price) AS low,
    last(price, timestamp) AS close,
    sum(base_amount) AS volume,
    count(*) AS trade_count
FROM trades
GROUP BY bucket, base_asset_id, counter_asset_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('trades_1m',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);

-- 1-hour OHLCV
CREATE MATERIALIZED VIEW IF NOT EXISTS trades_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', bucket) AS bucket,
    base_asset_id,
    counter_asset_id,
    first(open, bucket) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, bucket) AS close,
    sum(volume) AS volume,
    sum(trade_count) AS trade_count
FROM trades_1m
GROUP BY time_bucket('1 hour', bucket), base_asset_id, counter_asset_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('trades_1h',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);
