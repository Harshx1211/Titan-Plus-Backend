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

@app.middleware("http")
async def log_requests(request, call_next):
    origin = request.headers.get("origin")
    print(f"📥 {request.method} {request.url.path} from {origin}")
    response = await call_next(request)
    return response


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/")
async def root():
    return {
        "status": "Titan Crypto Brain V3.1 Online", 
        "mode": "24/7 Analysis",
        "supported_coins": ["BTC", "ETH", "SOL", "DOGE"]
    }

@app.get("/api/signals")
async def get_signals():
    # Fetch last 10 signals from Supabase
    res = db.supabase.table("trades").select("*").order("created_at", desc=True).limit(10).execute()
    return res.data

@app.get("/api/thoughts")
async def get_thoughts():
    # Fetch last 15 brain thoughts
    res = db.supabase.table("brain_logs").select("*").order("created_at", desc=True).limit(15).execute()
    return res.data

@app.websocket("/ws/market")
async def websocket_endpoint(websocket: WebSocket):
    # Log origin for debugging
    origin = websocket.headers.get("origin")
    print(f"🔌 WebSocket link attempt from origin: {origin}")
    try:
        await websocket.accept()
        print(f"✅ WebSocket connection established")
        while True:
            # Stream the latest active trade and market state
            active_trade = db.get_active_trade()
            await websocket.send_json({
                "type": "update", 
                "active_trade": active_trade,
                "timestamp": datetime.now().isoformat()
            })
            await asyncio.sleep(5)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print(f"🔌 WebSocket link closed")
        try:
            await websocket.close()
        except:
            pass

# Serve the built React frontend (fallback) - Moved to prevent route shadowing
if os.path.exists("dashboard/dist"):
    app.mount("/dashboard", StaticFiles(directory="dashboard/dist", html=True), name="static")

if __name__ == "__main__":
    # Hugging Face usually provides the port via an environment variable, otherwise 7860
    port = int(os.getenv("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")
