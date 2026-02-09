import optuna
import xgboost as xgb
import pandas as pd
import numpy as np
import logging
import json
import joblib
from sklearn.model_selection import train_test_split, cross_val_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("optimizer")

class OptunaOptimizer:
    def __init__(self, data_path="data/training_data.csv", model_path="models/xgboost_optimized.json"):
        self.data_path = data_path
        self.model_path = model_path
        self.study = None
        self._cached_data = None

    def load_data(self):
        """Loads data from Supabase (preferred) or CSV (fallback). Returns (X, y)."""
        if self._cached_data: return self._cached_data
        
        df = None
        # 1. Try Loading from Supabase
        try:
            from infrastructure import SupabaseManager
            db = SupabaseManager()
            history = db.get_history(limit=50000) # Fetch up to 50k recent trades
            if history:
                df = pd.DataFrame(history)
                # Ensure we have target
                if 'profit_loss' in df.columns and 'target' not in df.columns:
                     df['target'] = (df['profit_loss'] > 0).astype(int)
        except Exception as e:
            logger.warning(f"Supabase Load Failed: {e}. Falling back to CSV.")
            
        # 2. Fallback to CSV
        if df is None:
            try:
                df = pd.read_csv(self.data_path)
            except Exception as e:
                logger.error(f"CSV Load Error: {e}")
                return None, None
                
        # 3. Preprocess
        try:
            target_col = 'target' if 'target' in df.columns else ('outcome' if 'outcome' in df.columns else None)
            if not target_col: return None, None
            
            # Select feature columns (assumes features are numeric and not metadata)
            exclude = ['id', 'timestamp', 'symbol', 'decision_id', 'strategy', 'reasoning', target_col]
            features = [c for c in df.columns if c not in exclude and np.issubdtype(df[c].dtype, np.number)]
            
            X = df[features]
            y = df[target_col]
            
            self._cached_data = (X, y)
            return X, y
        except Exception as e:
             logger.error(f"Preprocessing Failed: {e}")
             return None, None

    def objective(self, trial):
        """
        Optuna Objective Function using Cross-Validation.
        """
        X, y = self.load_data()
        if X is None: return 0.0

        param = {
            'verbosity': 0,
            'objective': 'binary:logistic',
            'n_estimators': trial.suggest_int('n_estimators', 100, 1000),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
            'subsample': trial.suggest_float('subsample', 0.6, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
            'gamma': trial.suggest_float('gamma', 0, 0.5),
            'reg_alpha': trial.suggest_float('reg_alpha', 0, 1.0),
            'reg_lambda': trial.suggest_float('reg_lambda', 1, 3.0),
            'n_jobs': 1 # XGBoost threads inside CV
        }

        model = xgb.XGBClassifier(**param)
        
        # [Expert Upgrade] Robust 5-Fold Cross-Validation
        scores = cross_val_score(model, X, y, cv=5, scoring='precision')
        return scores.mean()

    def optimize(self, n_trials=50):
        logger.info(f"Starting Optimization with {n_trials} trials...")
        self.study = optuna.create_study(direction="maximize")
        
        # [Expert Upgrade] Parallel Execution + Early Stopping
        self.study.optimize(
            self.objective, 
            n_trials=n_trials, 
            n_jobs=-1, # Use all cores
            callbacks=[lambda study, trial: study.stop() if study.best_value > 0.85 else None]
        )
        
        logger.info("Optimization Complete.")
        logger.info(f"Best Params: {self.study.best_params}")
        logger.info(f"Best Mean Precision (CV): {self.study.best_value}")
        
        self.save_best_model()

    def save_best_model(self):
        if not self.study: return
        
        X, y = self.load_data()
        best_params = self.study.best_params
        
        final_model = xgb.XGBClassifier(**best_params)
        final_model.fit(X_train, y_train)
        
        final_model.save_model(self.model_path)
        logger.info(f"Optimized model saved to {self.model_path}")
        
        # Save params separately
        with open(self.model_path.replace('.json', '_params.json'), 'w') as f:
            json.dump(best_params, f, indent=4)

if __name__ == "__main__":
    # Test Run (Requires csv data)
    # opt = OptunaOptimizer()
    # opt.optimize(n_trials=10)
    pass
