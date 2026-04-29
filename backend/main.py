"""
CrowdPulse FastAPI backend.
"""

from contextlib import asynccontextmanager
from datetime import datetime
import asyncio
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, hotels, location, predict, suggest
from utils.ws_manager import ConnectionManager

manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from ml.predictor import get_predictor

    get_predictor()
    task = asyncio.create_task(broadcast_loop())
    yield
    task.cancel()


app = FastAPI(
    title="CrowdPulse Real-Time API",
    version="3.0.0",
    description="Real-time crowd prediction for user-entered places with optional Groq enrichment.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5500", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(predict.router, prefix="/predict", tags=["Prediction"])
app.include_router(suggest.router, prefix="/suggest", tags=["Suggestions"])
app.include_router(hotels.router, prefix="/hotels", tags=["Hotels"])
app.include_router(location.router, prefix="/location", tags=["Location"])


async def broadcast_loop():
    from ml.predictor import get_predictor

    predictor = get_predictor()
    while True:
        if manager.active_connections:
            snapshot = predictor.get_all_live()
            await manager.broadcast(
                json.dumps(
                    {
                        "type": "crowd_update",
                        "timestamp": datetime.now().isoformat(),
                        "locations": snapshot,
                        "summary": {
                            "total": len(snapshot),
                            "high": sum(1 for row in snapshot if row["level"] == "high"),
                            "medium": sum(1 for row in snapshot if row["level"] == "medium"),
                            "low": sum(1 for row in snapshot if row["level"] == "low"),
                            "avg_pct": round(sum(row["crowd_pct"] for row in snapshot) / len(snapshot), 1),
                        },
                    }
                )
            )
        await asyncio.sleep(5)


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        from ml.predictor import get_predictor

        await websocket.send_text(
            json.dumps(
                {
                    "type": "initial_state",
                    "timestamp": datetime.now().isoformat(),
                    "locations": get_predictor().get_all_live(),
                }
            )
        )
        while True:
            await asyncio.wait_for(websocket.receive_text(), timeout=30)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        manager.disconnect(websocket)


@app.get("/")
def root():
    return {
        "name": "CrowdPulse Real-Time API",
        "version": "3.0.0",
        "status": "live",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
