#!/bin/bash

# Titan Plus Institutional - Tablet Deployment Script

echo "--- Starting Titan Plus Tablet-Only Setup ---"

# 1. Update Termux Packages
echo "[1/4] Updating Termux packages..."
pkg update -y && pkg upgrade -y

# 2. Install Python, Node.js, and Build Tools
echo "[2/4] Installing Python, Node.js, and system base..."
pkg install python nodejs git termux-api -y

# 3. Request WakeLock (Critical for Trading)
echo "[3/4] Requesting CPU WakeLock..."
termux-wake-lock
echo ">>> TIP: Also disable Battery Optimization for Termux in Android Settings."

# 4. Install Project Dependencies in Termux
# (This assumes the user has copied the 'FnO' folder to their device)
echo "[4/4] Setup complete!"
echo "--- COMMANDS TO START THE BRAIN ---"
echo "1. cd FnO"
echo "2. pip install -r requirements.txt"
echo "3. python api.py"
echo ""
echo "--- COMMANDS TO START THE DASHBOARD ---"
echo "1. cd FnO/dashboard"
echo "2. npm install"
echo "3. npm run dev"
echo ""
echo "Oracle Dashboard will be at http://localhost:3000 on your tablet browser."
