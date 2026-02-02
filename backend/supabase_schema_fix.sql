-- ============================================
-- Titan Plus - FULL Supabase Schema Fix (v3)
-- ============================================
-- Run this in your Supabase SQL Editor to add ALL missing columns.
-- This restores 100% functionality for historical tracking and learning.

-- 1. Update 'brain_snapshots' table
ALTER TABLE brain_snapshots 
ADD COLUMN IF NOT EXISTS signal_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS decision VARCHAR(20) DEFAULT 'UNKNOWN',
ADD COLUMN IF NOT EXISTS regime VARCHAR(50) DEFAULT 'UNCERTAIN',
ADD COLUMN IF NOT EXISTS efficacy INTEGER DEFAULT 0;

-- 2. Update 'signal_ledger' table  
ALTER TABLE signal_ledger 
ADD COLUMN IF NOT EXISTS persistence BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS timestamp_ns BIGINT,
ADD COLUMN IF NOT EXISTS seq_id BIGINT,
ADD COLUMN IF NOT EXISTS regime VARCHAR(50) DEFAULT 'UNCERTAIN';

-- 3. Add Indexes for high-performance dashboard queries
CREATE INDEX IF NOT EXISTS idx_brain_snapshots_decision ON brain_snapshots(decision);
CREATE INDEX IF NOT EXISTS idx_brain_snapshots_regime ON brain_snapshots(regime);
CREATE INDEX IF NOT EXISTS idx_signal_ledger_persistence ON signal_ledger(persistence);
CREATE INDEX IF NOT EXISTS idx_signal_ledger_regime ON signal_ledger(regime);

-- 4. Verification Check
SELECT 
    table_name, 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_name IN ('brain_snapshots', 'signal_ledger')
ORDER BY table_name, ordinal_position;

-- ============================================
-- Expected Results:
-- brain_snapshots: decision, regime, efficacy, features, outcome, stage, timestamp...
-- signal_ledger: signal_id, timestamp, symbol, regime, state, value, persistence, seq_id, timestamp_ns...
-- ============================================
