import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import pickle
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
from brain_engine_ml import BrainEngineML
from infrastructure import SupabaseManager

def extract_training_data(limit=2000):
    """Extract and link snapshots with ledger outcomes using fuzzy timestamp matching"""
    print(f"Connecting to Supabase for data extraction...")
    db = SupabaseManager()
    
    # 1. Fetch Ledger Outcomes
    print("Fetching signal_ledger outcomes...")
    ledger_res = db.supabase.table('signal_ledger').select('signal_id, value, timestamp').eq('state', 'OUTCOME').execute()
    ledger_data = ledger_res.data
    if not ledger_data:
        print("ERROR: No outcomes found in signal_ledger")
        return None
    
    # Parse ledger timestamps
    for l in ledger_data:
        try:
            l['dt'] = pd.to_datetime(l['timestamp'])
        except:
            l['dt'] = None
    
    print(f"  Got {len(ledger_data)} outcomes from ledger")
    
    # 2. Fetch Snapshots
    print("Fetching trade_snapshots (Production Data)...")
    snaps_res = db.supabase.table('trade_snapshots').select('*').order('timestamp', desc=True).limit(limit).execute()
    snapshots = snaps_res.data
    if not snapshots:
        print("ERROR: No snapshots found")
        return None
    
    print(f"  Analysing {len(snapshots)} snapshots...")
    
    training_data = []
    found_matches = 0
    
    for snap in snapshots:
        try:
            snap_time = pd.to_datetime(snap.get('timestamp'))
            if not snap_time: continue
            
            # Fuzzy Matching: Look for ledger entry within 30 seconds
            # (Widened from 5s to be safe for older logs)
            match_outcome = None
            for l in ledger_data:
                if l['dt'] and abs((l['dt'] - snap_time).total_seconds()) < 30:
                    match_outcome = l['value']
                    break
            
            if not match_outcome:
                continue
                
            # Parse Features
            features_raw = snap.get('features', {})
            features = features_raw
            if isinstance(features_raw, str):
                try:
                    features = json.loads(features_raw)
                except:
                    continue
            
            if not isinstance(features, dict) or 'ADX' not in features:
                continue
            
            # Extract ML Features
            adx = float(features.get('ADX', 25.0))
            basis_res = float(features.get('BASIS_RES', 0.5))
            pcr = float(features.get('PCR', 1.0))
            oi_res = float(features.get('OI_RES', 0.5))
            
            regime_str = snap.get('regime', 'UNCERTAIN')
            regime_map = {'TRENDING': 0, 'SIDEWAYS_STRONG': 1, 'SIDEWAYS_NORMAL': 2, 'SIDEWAYS_WEAK': 3, 'UNCERTAIN': 4}
            regime_encoded = regime_map.get(str(regime_str).upper(), 4)
            
            # Label from matched outcome: WIN=1, LOSS=0
            label = 1 if match_outcome == 'WIN' else 0
            
            training_data.append({
                'ADX': adx, 'BASIS_RES': basis_res, 'PCR': pcr, 'OI_RES': oi_res,
                'REGIME': regime_encoded, 'ADX_OI': adx * oi_res, 'PCR_DEV': abs(pcr - 1.0),
                'label': label
            })
            found_matches += 1
            
        except Exception as e:
            continue
            
    print(f"DONE: Successfully matched {found_matches} snapshots with outcomes via timestamp")
    
    if len(training_data) < 5:
        print(f"ERROR: Only {len(training_data)} linked samples found. Need more data.")
        return None
        
    df = pd.DataFrame(training_data)
    print(f"Label distribution: {df['label'].value_counts().to_dict()}")
    return df

def train_model(df):
    """Train XGBoost model"""
    print("\nTraining XGBoost model...")
    
    feature_cols = ['ADX', 'BASIS_RES', 'PCR', 'OI_RES', 'REGIME', 'ADX_OI', 'PCR_DEV']
    X = df[feature_cols].values
    y = df['label'].values
    
    if len(np.unique(y)) < 2:
        print("ERROR: Training set only contains one class. Need both successes and failures.")
        return None

    label_counts = df['label'].value_counts()
    stratify_target = y if (len(label_counts) > 1 and label_counts.min() > 1) else None

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=stratify_target
    )
    
    brain = BrainEngineML()
    brain.train_model(X_train, y_train)
    
    # Evaluate
    X_test_scaled = brain.scaler.transform(X_test)
    y_pred = brain.model.predict(X_test_scaled)
    y_proba = brain.model.predict_proba(X_test_scaled)[:, 1] if hasattr(brain.model, 'predict_proba') else y_pred
    
    print("\n=== MODEL EVALUATION ===")
    print(classification_report(y_test, y_pred))
    
    print("\nFeature Importance:")
    importances = brain.model.feature_importances_
    for feat, imp in sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True):
        print(f"  {feat:15s}: {imp:.3f}")
    
    return brain

def main():
    df = extract_training_data()
    if df is not None:
        model = train_model(df)
        if model:
            print("\nDONE: Stage 2 Brain trained and saved.")

if __name__ == "__main__":
    main()
