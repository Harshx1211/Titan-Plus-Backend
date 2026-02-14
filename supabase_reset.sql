-- 1. DROP LEGACY TABLES
DROP TABLE IF EXISTS signal_ledger CASCADE;
DROP TABLE IF EXISTS trade_snapshots CASCADE;
DROP TABLE IF EXISTS system_heartbeat CASCADE;

-- 2. CREATE NEW TITAN CRYPTO TABLES

-- Trades table for position management and history
CREATE TABLE trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    side TEXT CHECK (side IN ('LONG', 'SHORT')),
    entry_price DECIMAL NOT NULL,
    exit_price DECIMAL,
    status TEXT CHECK (status IN ('OPEN', 'CLOSED')) DEFAULT 'OPEN',
    pnl DECIMAL,
    entry_reason TEXT,
    exit_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);

-- Brain Logs for AI training & thinking process
CREATE TABLE brain_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    sentiment TEXT,
    logic_details JSONB,
    market_regime TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Market State snapshots
CREATE TABLE market_state (
    symbol TEXT PRIMARY KEY,
    price DECIMAL NOT NULL,
    volume DECIMAL,
    rsi DECIMAL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. ENABLE ROW LEVEL SECURITY (Optional but recommended)
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_state ENABLE ROW LEVEL SECURITY;

-- Allow all for now (development mode)
CREATE POLICY "Allow all for authenticated users" ON trades FOR ALL USING (true);
CREATE POLICY "Allow all for authenticated users" ON brain_logs FOR ALL USING (true);
CREATE POLICY "Allow all for authenticated users" ON market_state FOR ALL USING (true);
