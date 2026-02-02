-- ============================================
-- Titan Plus - Supabase Schema Fix
-- ============================================
-- Run this in your Supabase SQL Editor to add missing columns
-- This is OPTIONAL - the code will work without these columns

-- 1. Add missing columns to brain_snapshots table
ALTER TABLE brain_snapshots 
ADD COLUMN IF NOT EXISTS decision VARCHAR(20) DEFAULT 'UNKNOWN',
ADD COLUMN IF NOT EXISTS efficacy INTEGER DEFAULT 0;

-- 2. Add missing columns to signal_ledger table  
ALTER TABLE signal_ledger 
ADD COLUMN IF NOT EXISTS persistence BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS seq_id BIGINT;

-- Add indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_brain_snapshots_decision ON brain_snapshots(decision);
CREATE INDEX IF NOT EXISTS idx_signal_ledger_persistence ON signal_ledger(persistence);

-- 3. Verify the changes
SELECT 
    table_name, 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_name IN ('brain_snapshots', 'signal_ledger')
ORDER BY table_name, ordinal_position;

-- ============================================
-- Expected Output:
-- ============================================
-- brain_snapshots should now have 'decision' column (VARCHAR)
-- signal_ledger should now have 'persistence' column (BOOLEAN)
--
-- If you see these columns in the output, the fix is complete!
-- ============================================
