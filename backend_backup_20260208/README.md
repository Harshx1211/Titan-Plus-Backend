---
title: Titan Plus Oracle
emoji: 🧠
colorFrom: indigo
colorTo: blue
sdk: docker
pinned: false
app_port: 7860
---

# Titan Plus Oracle - Backend

Institutional-grade trading intelligence engine with XGBoost decision core and self-evolving reinforcement learning.

## Deployment on Hugging Face Spaces

This Space runs the Titan Plus FastAPI backend inside a Docker container. 

### Configuration Required:
Ensure you add the following secrets in **Settings > Variables and Secrets**:
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `GROWW_COOKIE` (if using Groww)
- `GROWW_X_CLIENT_ID` (if using Groww)
- `SHADOW_MODE` (true/false)
