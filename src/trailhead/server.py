"""
Trailhead Local Web Server (FastAPI + Server-Sent Events)
Provides:
- GET / : single-file local UI
- GET /api/status : local health, netguard counter, model reachability, and RUN_ENV
- POST /api/trail : streaming Server-Sent Events (SSE) with live tool trace
- GET /api/svg : self-contained SVG radial graph
"""
import asyncio
import json
import queue
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Body, FastAPI, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, StreamingResponse
import httpx

from trailhead.config import MODEL_MAIN, OLLAMA_HOST
from trailhead.models import Trail
from trailhead.netguard import get_blocked_attempts
from trailhead.pipeline import run_pipeline
from trailhead.render import render_trail_svg

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Trailhead", description="Offline issue-to-code trail finder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_WEB_DIR = Path(__file__).parent / "web"
_ROOT_DIR = Path(__file__).resolve().parent.parent.parent

# Cache the latest computed trail for SVG rendering
_LATEST_TRAIL: Optional[Trail] = None

@app.get("/", response_class=HTMLResponse)
def index_page():
    """Serve single-file zero-dependency web interface."""
    html_file = _WEB_DIR / "index.html"
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="web/index.html not found")
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))

@app.get("/api/status")
def get_status():
    """Return local offline status, netguard blocked connections, and model health."""
    ollama_reachable = False
    try:
        with httpx.Client(timeout=httpx.Timeout(1.0, connect=0.5)) as client:
            res = client.get(f"{OLLAMA_HOST}/api/tags")
            if res.status_code == 200:
                ollama_reachable = True
    except Exception:
        ollama_reachable = False

    env_data: Dict[str, Any] = {}
    env_file = _ROOT_DIR / "RUN_ENV.json"
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                env_data = json.load(f)
        except Exception:
            pass

    return {
        "status": "ok",
        "netguard": {"blocked_attempts": get_blocked_attempts()},
        "model": MODEL_MAIN,
        "ollama_reachable": ollama_reachable,
        "env": env_data,
    }

@app.get("/api/svg")
def get_svg(repo: Optional[str] = Query(default=None)):
    """Return latest generated trail as pure SVG with image/svg+xml header."""
    global _LATEST_TRAIL
    if _LATEST_TRAIL is not None:
        svg_content = render_trail_svg(_LATEST_TRAIL)
    else:
        # Generate dummy placeholder SVG
        dummy_trail = Trail(status="graph_only", confidence="medium")
        svg_content = render_trail_svg(dummy_trail)
    return Response(content=svg_content, media_type="image/svg+xml")

@app.get("/api/graph", response_class=HTMLResponse)
@app.get("/graphify", response_class=HTMLResponse)
def get_complex_graph(repo: Optional[str] = Query(default=None)):
    """Return full complex interactive Graphify visualizer (437 nodes, 973 edges, 15 communities)."""
    if repo:
        repo_path = Path(repo)
        candidate = repo_path / "graphify-out" / "graph.html"
        if candidate.exists():
            return HTMLResponse(content=candidate.read_text(encoding="utf-8"))

    root_graph = _ROOT_DIR / "graphify-out" / "graph.html"
    if root_graph.exists():
        return HTMLResponse(content=root_graph.read_text(encoding="utf-8"))

    raise HTTPException(status_code=404, detail="graphify-out/graph.html not found")

@app.post("/api/trail")
async def stream_trail(payload: Dict[str, Any] = Body(...)):
    """Execute pipeline and stream Server-Sent Events (SSE) live to client."""
    repo = payload.get("repo", "")
    issue_text = payload.get("issue_text", "")
    model = payload.get("model", MODEL_MAIN)

    if not repo or not issue_text:
        raise HTTPException(status_code=400, detail="Both 'repo' and 'issue_text' are required")

    event_queue: queue.Queue = queue.Queue()

    def run_worker():
        global _LATEST_TRAIL
        try:
            def on_event(ev_type: str, data: Any):
                event_queue.put((ev_type, data))

            trail = run_pipeline(
                repo_path=repo,
                issue_text=issue_text,
                use_llm=True,
                model=model,
                on_event=on_event,
            )
            _LATEST_TRAIL = trail
        except Exception as e:
            event_queue.put(("error", str(e)))
        finally:
            event_queue.put(None)  # Sentinel to end stream

    threading.Thread(target=run_worker, daemon=True).start()

    async def sse_generator():
        while True:
            # Non-blocking poll
            try:
                item = event_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.05)
                continue

            if item is None:
                break

            ev_type, data = item
            data_str = json.dumps(data) if not isinstance(data, str) else data
            yield f"event: {ev_type}\ndata: {data_str}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")
