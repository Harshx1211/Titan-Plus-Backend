# Titan Plus - ML Trading Engine (Distribution Kit)

Welcome to the distribution package for Titan Plus. This kit provides the core ML engine, infrastructure connectors, and data models required to run the advanced trading logic.

## Prerequisites

- Python 3.10+
- A Supabase project (for data persistence)
- Basic understanding of Python environments

## Setup

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements_distribution.txt
    ```

2.  **Environment Configuration:**
    Copy `.env.example` to `.env` and fill in your credentials:
    ```bash
    cp .env.example .env
    ```
    Required keys:
    - `SUPABASE_URL`: Your Supabase Project URL
    - `SUPABASE_KEY`: Your Supabase Service Role Key (or Anon Key if policies allow)

3.  **Database Setup:**
    Run the SQL commands from `DATABASE_SCHEMA.sql` in your Supabase SQL Editor to set up the necessary tables (`trade_snapshots`, `signal_ledger`, `brain_snapshots`).

## Usage

### 1. Training the Brain
This script connects to your database, fetches historical trade snapshots, and trains the XGBoost model.
```bash
python train_brain.py
```

### 2. Integration
Refer to `INTEGRATION.md` for details on how to import and use the `BrainEngineML` in your own strategies.

## Core Components

- **`infrastructure.py`**: Handles database connections and data persistence. Now includes `get_last_known_prices` for state recovery.
- **`brain_engine_ml.py`**: The core logic engine containing the XGBoost model, feature processing, and decision gates.
- **`models.py`**: Pydantic models for type safety.

## Updates (v9.9.8)
- **State Persistence**: The system now recovers the last known active prices from the database on startup.
- **Realistic Fallbacks**: Updated fallback mechanisms to prevent "25,000" placeholders.
