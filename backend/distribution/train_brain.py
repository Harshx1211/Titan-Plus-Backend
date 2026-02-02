#!/usr/bin/env python3
"""
Training script for Brain ML model
Extracts data from database and trains XGBoost
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
from brain_engine_ml import BrainEngineML
from infrastructure import SupabaseManager

def extract_training_data(days=60, min_samples=200):
    """Extract and prepare training data from database"""
    print(f"Extracting training data from last {days} days...")
    
    db = SupabaseManager()
    snapshots = db.get_snapshots(limit=2000)
    
    if not snapshots:
        print("ERROR: No data found in database")
        return None
    
    training_data = []
    
    for snap in snapshots:
        try:
            features = snap.get('features', {})
            if not features: continue
            
            # Parse features
            adx = float(features.get('ADX', 25.0))
            basis_res = float(features.get('BASIS_RES', 0.5))
            pcr = float(features.get('PCR', 1.0))
            oi_res = float(features.get('OI_RES', 0.5))
            
            # Get regime
            regime_str = features.get('regime', 'UNCERTAIN')
            regime_map = {
                'TRENDING': 0, 'SIDEWAYS_STRONG': 1, 'SIDEWAYS_NORMAL': 2,
                'SIDEWAYS_WEAK': 3, 'UNCERTAIN': 4
            }
            regime_encoded = regime_map.get(regime_str, 4)
            
            # Get outcome
            mfe = float(features.get('mfe', 0.0))
            mae = float(features.get('mae', 0.0))
            decision = snap.get('decision', 'BLOCK')
            
            # Label logic: 1 if successful trade (for Approvals) or successful block (for Blocks)
            if decision == 'APPROVE':
                label = 1 if (mfe > 2 * mae and mfe > 10) else 0
            else:
                label = 1 if (mfe < 10 or mfe < mae) else 0
            
            training_data.append({
                'ADX': adx, 'BASIS_RES': basis_res, 'PCR': pcr, 'OI_RES': oi_res,
                'REGIME': regime_encoded, 'ADX_OI': adx * oi_res, 'PCR_DEV': abs(pcr - 1.0),
                'label': label, 'decision': decision
            })
            
        except Exception as e:
            continue
    
    if len(training_data) < min_samples:
        print(f"ERROR: Only {len(training_data)} samples found, need {min_samples}")
        return None
    
    df = pd.DataFrame(training_data)
    print(f"✓ Extracted {len(df)} samples ({df['label'].mean():.1%} positive)")
    return df

def train_model(df):
    """Train XGBoost model"""
    print("\nTraining XGBoost model...")
    
    feature_cols = ['ADX', 'BASIS_RES', 'PCR', 'OI_RES', 'REGIME', 'ADX_OI', 'PCR_DEV']
    X = df[feature_cols].values
    y = df['label'].values
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    brain = BrainEngineML()
    brain.train_model(X_train, y_train)
    
    # Evaluate
    X_test_scaled = brain.scaler.transform(X_test)
    y_pred = brain.model.predict(X_test_scaled)
    y_proba = brain.model.predict_proba(X_test_scaled)[:, 1]
    
    print("\n=== MODEL EVALUATION ===")
    print(classification_report(y_test, y_pred))
    print(f"ROC-AUC: {roc_auc_score(y_test, y_proba):.3f}")
    
    print("\nFeature Importance:")
    importances = brain.model.feature_importances_
    for feat, imp in sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True):
        print(f"  {feat:15s}: {imp:.3f}")
    
    return brain

def main():
    df = extract_training_data()
    if df is not None:
        train_model(df)
        print("\n✓ Training complete and model saved.")

if __name__ == "__main__":
    main()
