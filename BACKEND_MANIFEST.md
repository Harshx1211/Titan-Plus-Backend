# 🤖 Titan Plus Institutional Engine: Backend Manifest

This document provides a comprehensive overview of the backend architecture for verification. This single file explains every component needed to run and validate the system.

---

## 🏗️ 1. Deployment Essentials (Root Folder)
These files define the environment and how the application starts.

| File Name | Description |
| :--- | :--- |
| `Dockerfile` | Master build instructions for the container (Installs Python, ML libs, and dependencies). |
| `Procfile` | The startup command used by production servers (Hugging Face / Heroku). |
| `requirements.txt` | The master list of all Python dependencies (Pandas, FastAPI, XGBoost, etc.). |
| `.env` | Environment secrets (Supabase URL, API Keys, Telegram Token). |
| `README.md` | General project overview and setup instructions. |

---

## 🧠 2. Core Backend Logic (`/backend` Folder)
The primary engine files that handle the heavy lifting.

| File Name | Description |
| :--- | :--- |
| **api.py** | **The Orchestrator.** Entry point for the FastAPI server and starts all background loops. |
| **infrastructure.py** | **The Backbone.** Manages Database connections, Lead Election (High Availability), and Heartbeats. |
| **config.py** | **The Brain Center.** Centralized settings, versioning, and global thresholds. |
| **brain_unified.py** | **The Decision Engine.** Merges XGBoost, RL, and SMC logic into a single trading decision. |
| **smc_engine.py** | **The Structure Engine.** Detects Smart Money Concepts like Order Blocks and Fair Value Gaps. |
| **providers.py** | **The Data Bridge.** Interfaces with Shoonya (Finvasia), Groww, and Fallback scrapers. |
| **crypto_provider.py** | **The Global Loop.** Specialized 24/7 data provider for BTC/ETH and Global indices. |
| **execution_engine.py** | **The Trader.** Handles real-time order execution, stop-losses, and profit targets. |
| **models_v3.py** | **The Schema.** Defines all Pydantic models for type safety and database mappings. |
| **outcome_tracker.py** | **The Auditor.** Automatically tracks trade PnL and calculates system accuracy. |
| **signal_notifier.py** | **The Messenger.** Formats and sends approved signals to Telegram and the Frontend. |
| **strategist.py** | **The Context.** Identifies Market Regimes (Trending, Sideways, Neutral). |
| **health_check_endpoint.py** | **The Monitor.** Detailed internal health check for CPU, RAM, and thread status. |
| **config_validator.py** | **The Guard.** Runs on startup to ensure all credentials and settings are valid. |
| **engines.py** | **The Safety.** Contains the Data Sentinel, Risk Engine, and Pattern Vetoes. |

---

## 📁 3. Specialized Directories
| Directory | Purpose |
| :--- | :--- |
| `grandmaster/` | Highly specialized logic for Option Greeks, Volatility Skew, and Macro analysis. |
| `notifier/` | Contains the Telegram client and message templates. |
| `scripts/` | **Verification tools.** Contains `verify_heuristics.py` and simulation scripts. |
| `docs/` | Internal technical documentation and integration guides. |
| `distribution/` | SQL schemas for Supabase and legacy integration notes. |

---

## ✅ 4. How to Verify Perfection
Instructions for your friend to confirm the system is working:

1.  **Dependency Check**: Run `pip install -r requirements.txt`. It must install without conflicts.
2.  **Heuristic Logic Test**: 
    ```bash
    python backend/scripts/verify_heuristics.py
    ```
    *Should output: "✅ Logic Verification Passed"*
3.  **Startup & Leader Election**: 
    ```bash
    python backend/api.py
    ```
    *Check logs for: "Promoted to LEADER" and "System Fully Operational."*
4.  **Health Audit**: Visit `http://localhost:8004/api/health/detailed` to see the live status of all sub-engines.

---
*Generated for the Titan Plus Helios Release (v15.3.6)*
