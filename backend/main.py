"""
ViewForge — YouTube Browser Automation Tool
FastAPI backend with WebSocket live log streaming.
Serves the built React frontend as static files so the whole app
runs on a single URL (http://localhost:8000).
"""
import asyncio
import json
import os
import pathlib
from contextlib import asynccontextmanager
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import init_db
from routers import accounts, proxies, campaigns, logs, stats, auth
from automation.engine import set_broadcast_callback
import broadcast as _broadcast_module


# ── WebSocket connection manager ──────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, data: dict):
        dead = set()
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.active.discard(ws)


ws_manager = ConnectionManager()


async def broadcast_log(data: dict):
    await ws_manager.broadcast(data)


# ── Scheduler (daily reset of account session counts) ─────────────────────────

scheduler = AsyncIOScheduler()

def _daily_reset():
    from database import SessionLocal
    import models
    db = SessionLocal()
    try:
        db.query(models.Account).update({
            models.Account.daily_session_count: 0,
        })
        db.commit()
    finally:
        db.close()


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB tables
    init_db()
    os.makedirs(os.getenv("PROFILES_DIR", "./profiles"), exist_ok=True)

    # Register WebSocket log broadcaster (engine + account creator)
    set_broadcast_callback(broadcast_log)
    _broadcast_module.set_fn(broadcast_log)

    # Scheduler: reset daily counts at midnight
    scheduler.add_job(_daily_reset, "cron", hour=0, minute=0)
    scheduler.start()

    yield

    scheduler.shutdown()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ViewForge API",
    description="YouTube browser automation management API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(proxies.router)
app.include_router(campaigns.router)
app.include_router(logs.router)
app.include_router(stats.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# ── Serve built React frontend ────────────────────────────────────────────────
# Must be registered LAST so API routes take priority.
_DIST = pathlib.Path(__file__).parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")


@app.websocket("/ws/logs")
async def websocket_logs(ws: WebSocket):
    """Live log stream. Frontend connects here to receive real-time updates."""
    await ws_manager.connect(ws)
    try:
        while True:
            # Keep connection alive; broadcast is triggered by engine events
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)
