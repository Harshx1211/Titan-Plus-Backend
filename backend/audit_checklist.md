# Backend Audit Checklist - Phase 3 Integration

## 1. Core Intelligence Engines
- [ ] **Enhanced Brain Engine (`brain_engine_enhanced.py`)**
    - [ ] Verify `decide` method signature matches API calls.
    - [ ] Check legacy compatibility methods (`check_basis_stability`, `log_snapshot`).
    - [ ] Verify logic for combining XGBoost, RL, and SMC scores.
    - [ ] Confirm `save_state`/`load_state` persistence.
- [ ] **RL Evolution Engine (`rl_engine.py`)**
    - [ ] Verify PyTorch dependencies are handled (CPU-only).
    - [ ] Check state serialization/deserialization.
    - [ ] Confirm `get_recommendation` returns expected dictionary structure.
- [ ] **SMC Engine (`smc_engine.py`)**
    - [ ] Verify DataFrame input requirements (columns).
    - [ ] Check for potential `IndexError` in lookback windows.

## 2. API Orchestration (`api.py`)
- [ ] **Imports**: Verify all imports exist and are correctly named.
- [ ] **Initialization**: Confirm proper startup sequence (DB -> Providers -> Engines).
- [ ] **Endpoints**:
    - [ ] `/analyze`: Check if it correctly calls `DataSentinel`, `Strategist`, and `Brain`.
    - [ ] `/webhook/tradingview`: Verify signal parsing and signature verification.
- [ ] **Background Loop**:
    - [ ] Verify the `run_engine_loop` (assumed name from previous views) logic.
    - [ ] Check thread safety for `LiveState`.

## 3. Data & Infrastructure
- [ ] **Providers (`providers.py`)**
    - [ ] Check Shoonya/Groww API fallback logic.
    - [ ] Verify `get_market_snapshot` returns correct Pydantic model or dict.
- [ ] **Models (`models_v3.py`)**
    - [ ] Confirm all Pydantic models cover used fields in API and Engines.

## 4. Other Modules (Legacy & Support)
- [ ] **Evolution Engine (`evolution_engine.py`)**
    - [ ] Verify import of `EnhancedBrainEngine`.
    - [ ] Check `evolve_session` logic for compatibility.
- [ ] **Infrastructure (`infrastructure.py`)**
    - [ ] Database connection management.

## 5. Deployment
- [ ] **Dockerfile**
    - [ ] Check base image.
    - [ ] Verify PyTorch installation command.
    - [ ] Dependencies (`requirements.txt`) alignment.

## 6. Critical Findings & Fixes
*Log any issues found during the audit here.*
