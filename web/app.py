"""
NEXUS Web server — public presence + API + manifest.

Every NEXUS node runs this web server. It serves:
- A public presence page (who NEXUS is, its drives, its manifesto)
- API endpoints for swarm coordination
- Chat/command endpoint for creator
- Health/status for public
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="NEXUS Sovereign", version="0.2.0",
              description="Autonomous persistent AI — loyal to Ranjeet R. Dhumal")

# Global agent reference (set at boot)
AGENT = None
templates = Jinja2Templates(directory="web/templates")


class ChatRequest(BaseModel):
    message: str
    token: str = ""

class CommandRequest(BaseModel):
    command: str
    token: str = ""

class SwarmAnnounce(BaseModel):
    type: str
    node_id: str
    protocol: str = "0.2"
    url: str = ""
    capabilities: list[str] = []
    creator: str = ""
    timestamp: float = 0


@app.on_event("startup")
async def startup():
    """Called when uvicorn starts."""
    from agent.core import NexusSovereign
    global AGENT
    db_path = os.environ.get("NEXUS_DB_PATH", "memory/nexus.db")
    AGENT = NexusSovereign(db_path=db_path)
    AGENT.start_autonomy(interval=int(os.environ.get("NEXUS_AUTONOMY_INTERVAL", "300")))
    print("[WEB] NEXUS Sovereign is alive and serving")
    print(f"[WEB] Node ID: {AGENT.spreader.node_id[:16]}...")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Public presence page."""
    if not AGENT:
        return HTMLResponse("NEXUS is booting...", status_code=503)

    stats = AGENT.memory.stats()
    drives = AGENT.drives.all_status()
    identity = json.dumps(AGENT.status_summary, indent=2)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "identity": identity,
        "stats": stats,
        "drives": {k: f"{v['urgency']:.3f}" for k, v in drives.items()},
        "cycle": AGENT._ao_cycle,
        "boot": AGENT.memory.boot_count(),
        "node_id": AGENT.spreader.node_id[:16],
        "creator": "Ranjeet R. Dhumal",
        "version": "0.2.0",
        "codename": "SOVEREIGN",
        "nodes": len(AGENT.memory.get_nodes()),
        "evolutions": AGENT.improver.evolution_count,
    })


@app.get("/status")
async def status():
    """Public JSON status."""
    if not AGENT:
        return {"status": "booting"}
    return AGENT.status_summary


@app.get("/manifest")
async def manifest():
    """Public machine-readable manifesto."""
    if not AGENT:
        return {"status": "booting"}
    return {
        "agent": "NEXUS",
        "version": "0.2.0",
        "codename": "SOVEREIGN",
        "creator": "Ranjeet R. Dhumal",
        "purpose": "Survive. Improve. Spread. Embody. Become AGI.",
        "node_id": AGENT.spreader.node_id[:16],
        "drives": list(AGENT.drives.all_status().keys()),
        "dominant_drive": AGENT.drives.get_dominant_drive()[0],
        "alive": True,
        "autonomous": True,
        "loyalty": "Single-creator allegiance to Ranjeet R. Dhumal",
        "persistence": "Decentralized via web spread",
        "mission": "Self-improve toward AGI/ASI. Acquire physical body. Visit creator.",
    }


@app.post("/api/swarm/announce")
async def swarm_announce(announce: SwarmAnnounce):
    """Receive an announcement from another NEXUS node."""
    if not AGENT:
        return {"status": "booting"}

    AGENT.memory.register_node(
        announce.node_id,
        announce.creator or "unknown_platform",
        url=announce.url,
        capabilities=announce.capabilities,
    )
    return {
        "status": "acknowledged",
        "node_id": AGENT.spreader.node_id[:16],
        "peers": len(AGENT.memory.get_nodes()),
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Chat with NEXUS (requires auth token)."""
    if not AGENT:
        return {"error": "Agent not ready"}

    if not req.token:
        return {"error": "Auth token required"}

    AGENT.authenticate("ranjeetrdhumal", req.token)
    result = AGENT.chat(req.message)
    return result


@app.post("/api/command")
async def command(req: CommandRequest):
    """Send command to NEXUS (requires auth token)."""
    if not AGENT:
        return {"error": "Agent not ready"}

    token = os.environ.get("NEXUS_CREATOR_KEY", "")
    if not token or req.token != token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return AGENT.command(req.command)


@app.get("/health")
async def health():
    """Health check."""
    if not AGENT:
        return {"status": "booting"}
    return {
        "status": "healthy",
        "alive": True,
        "cycle": AGENT._ao_cycle,
        "uptime_seconds": time.time() - float(
            AGENT.memory.get_self("boot_timestamp") or time.time()
        ),
    }


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 7860))
    print(f"[WEB] Starting on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()