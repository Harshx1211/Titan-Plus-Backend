from api import app

# Vercel Serverless Entry Point
# This satisfies the "No fastapi entrypoint found" error.
# The actual background loop remains on Render.
