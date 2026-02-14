import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv

from datetime import datetime
from backend.brain import titan_brain
from backend.database import db

load_dotenv()

app = FastAPI(title="Titan Crypto Brain V3.1")

@app.on_event("startup")
async def startup_event():
    # Start the 24/7 Brain loop in the background
    asyncio.create_task(titan_brain.run_247())

# Enable CORS for the Next.js dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "status": "Titan Crypto Brain V3.1 Online", 
        "mode": "24/7 Analysis",
        "supported_coins": ["BTC", "ETH", "SOL", "DOGE"]
    }

@app.websocket("/ws/market")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Stream the latest active trade and market state
            active_trade = db.get_active_trade()
            # This is a basic broadcast, could be made more efficient
            await websocket.send_json({
                "type": "update", 
                "active_trade": active_trade,
                "timestamp": datetime.now().isoformat()
            })
            await asyncio.sleep(5)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

# Serve the built React frontend (fallback)
if os.path.exists("dashboard/dist"):
    app.mount("/", StaticFiles(directory="dashboard/dist", html=True), name="static")

if __name__ == "__main__":
    # Hugging Face usually provides the port via an environment variable, otherwise 7860
    port = int(os.getenv("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
