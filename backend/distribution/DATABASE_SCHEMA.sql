-- Create trade_snapshots table in Supabase
CREATE TABLE trade_snapshots (
    id BIGSERIAL PRIMARY KEY,
    features JSONB NOT NULL,
    decision TEXT,
    outcome INTEGER,
    stage INTEGER,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    efficacy INTEGER,
    regime TEXT
);

-- Add indexes for performance
CREATE INDEX idx_timestamp ON trade_snapshots(timestamp);
CREATE INDEX idx_decision ON trade_snapshots(decision);
CREATE INDEX idx_features ON trade_snapshots USING GIN(features);

-- Sample data format
/*
{
  "ADX": 35.0,
  "BASIS_RES": 0.8,
  "PCR": 0.9,
  "OI_RES": 0.7,
  "mfe": 25.0,
  "mae": 5.0,
  "regime": "TRENDING"
}
*/
