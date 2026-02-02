#!/bin/bash
# Quick start script for ML trading system Stage 2

echo "=========================================="
echo "ML Trading System - Stage 2 Quick Start"
echo "=========================================="

# 1. Install dependencies
echo "Installing dependencies..."
pip install -r requirements_ml.txt

# 2. Initial Training
echo "Extracting data and training initial model..."
python train_brain.py

# 3. Health check
echo "Running system health check..."
python -c "from brain_engine_ml import BrainEngineML; print(BrainEngineML().health_check())"

echo "=========================================="
echo "Setup Complete! To enable shadow mode, set SHADOW_MODE=true"
echo "=========================================="
