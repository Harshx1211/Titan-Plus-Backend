-- 1. CLEAR EXISTING DATA (Reset for Fresh Start)
TRUNCATE TABLE signal_ledger CASCADE;
TRUNCATE TABLE trade_snapshots CASCADE;
-- TRUNCATE TABLE outcome_ledger CASCADE; -- Only if you want to clear learning history

-- 2. ADD MISSING COLUMNS to signal_ledger (Fixes PGRST204)
-- Run these one by one or as a block. If a column exists, it will error (safe to ignore).

-- Metadata
ALTER TABLE signal_ledger ADD COLUMN IF NOT EXISTS brain_version TEXT;
ALTER TABLE signal_ledger ADD COLUMN IF NOT EXISTS generated_at TIMESTAMPTZ;

-- Brain Scores
ALTER TABLE signal_ledger ADD COLUMN IF NOT EXISTS confluence FLOAT;
ALTER TABLE signal_ledger ADD COLUMN IF NOT EXISTS xgb_score FLOAT;
ALTER TABLE signal_ledger ADD COLUMN IF NOT EXISTS rl_score FLOAT;
ALTER TABLE signal_ledger ADD COLUMN IF NOT EXISTS smc_score FLOAT;

-- Market Context
ALTER TABLE signal_ledger ADD COLUMN IF NOT EXISTS regime TEXT;
ALTER TABLE signal_ledger ADD COLUMN IF NOT EXISTS vix FLOAT;
ALTER TABLE signal_ledger ADD COLUMN IF NOT EXISTS volatility FLOAT;
ALTER TABLE signal_ledger ADD COLUMN IF NOT EXISTS volume FLOAT;

-- Smart Money / Support & Resistance
ALTER TABLE signal_ledger ADD COLUMN IF NOT EXISTS sr_data JSONB;

-- 3. VERIFY SCHEMA
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'signal_ledger';
