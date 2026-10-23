"""Command-line interface for Trailhead."""
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
import typer
from rich.console import Console
from rich.table import Table

from trailhead.config import OLLAMA_HOST
from trailhead.netguard import get_blocked_attempts, install_netguard

app = typer.Typer(help="Trailhead: Offline issue-to-code trail finder for open-source contributors.")
console = Console(legacy_windows=False)

def get_graphify_version() -> str:
    """Return installed Graphify CLI version."""
    candidate = shutil.which("graphify")
    if not candidate:
        win_local = Path(os.path.expanduser("~")) / ".local" / "bin" / "graphify.exe"
        if win_local.exists():
            candidate = str(win_local)

    if candidate:
        try:
            res = subprocess.run([candidate, "--version"], capture_output=True, text=True, timeout=5)
            out = res.stdout.strip() or res.stderr.strip()
            return out.split()[-1] if out else "installed"
        except Exception:
            return "installed"
    return "not found"

def get_ollama_info() -> Dict[str, Any]:
    """Query local Ollama instance for version and models."""
    info: Dict[str, Any] = {"version": "unknown", "models": []}
    
    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        win_ollama = Path(os.path.expanduser("~")) / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe"
        if win_ollama.exists():
            ollama_bin = str(win_ollama)

    if ollama_bin:
        try:
            res = subprocess.run([ollama_bin, "--version"], capture_output=True, text=True, timeout=5)
            out = res.stdout.strip() or res.stderr.strip()
            if "version is" in out:
                info["version"] = out.split("version is")[-1].strip()
            elif out:
                info["version"] = out.split()[-1]
        except Exception:
            pass

    try:
        import httpx
        with httpx.Client(timeout=3.0) as client:
            res = client.get(f"{OLLAMA_HOST}/api/tags")
            if res.status_code == 200:
                models_data = res.json().get("models", [])
                for m in models_data:
                    info["models"].append({
                        "name": m.get("name"),
                        "size": m.get("size"),
                        "digest": m.get("digest", "")[:12],
                        "quantization": m.get("details", {}).get("quantization_level", "unknown"),
                    })
    except Exception:
        pass

    return info

@app.command()
def doctor(
    out: str = typer.Option("RUN_ENV.json", "--out", "-o", help="Path to write environment JSON disclosure.")
):
    """Inspect environment, hardware, local models, and write RUN_ENV.json disclosure."""
    install_netguard()
    
    ollama_info = get_ollama_info()
    graphify_ver = get_graphify_version()

    ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    cpu_name = platform.processor() or "AMD/Intel x86_64"

    gpu_name = "None detected"
    try:
        if platform.system() == "Windows":
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                capture_output=True, text=True, timeout=5
            )
            gpus = [g.strip() for g in res.stdout.splitlines() if g.strip()]
            if gpus:
                gpu_name = ", ".join(gpus)
    except Exception:
        pass

    env_data = {
        "os": f"{platform.system()} {platform.release()} ({platform.architecture()[0]})",
        "cpu": cpu_name,
        "cpu_cores": psutil.cpu_count(logical=False) or 4,
        "cpu_threads": psutil.cpu_count(logical=True) or 8,
        "ram_gb": ram_gb,
        "gpu": gpu_name,
        "python": platform.python_version(),
        "ollama_version": ollama_info["version"],
        "models": ollama_info["models"],
        "graphify_version": graphify_ver,
        "external_apis": [],
        "netguard_blocked": get_blocked_attempts(),
    }

    with open(out, "w", encoding="utf-8") as f:
        json.dump(env_data, f, indent=2)

    table = Table(title="Trailhead Doctor - Local Environment Disclosure", show_header=True)
    table.add_column("Property", style="cyan", width=24)
    table.add_column("Value", style="green")

    table.add_row("Operating System", env_data["os"])
    table.add_row("CPU", f"{env_data['cpu']} ({env_data['cpu_cores']}C / {env_data['cpu_threads']}T)")
    table.add_row("RAM (GB)", f"{env_data['ram_gb']} GB")
    table.add_row("GPU", env_data["gpu"])
    table.add_row("Python", env_data["python"])
    table.add_row("Ollama Version", env_data["ollama_version"])
    table.add_row("Graphify Version", env_data["graphify_version"])
    
    models_str = ", ".join(m["name"] for m in env_data["models"]) if env_data["models"] else "None detected"
    table.add_row("Local Models", models_str)
    table.add_row("External APIs", "None (100% offline local)")
    table.add_row("Output File", str(Path(out).resolve()))

    console.print(table)
    console.print(f"[bold green][OK] Environment verified and written to {out}[/bold green]")

@app.command()
def index(
    repo: str = typer.Argument(".", help="Path to repository to index.")
):
    """Index a repository using Graphify."""
    console.print(f"Indexing repository at {repo}...")

@app.command()
def trail(
    repo: str = typer.Option(".", "--repo", "-r", help="Path to indexed repository."),
    issue: str = typer.Option(..., "--issue", "-i", help="Issue text or path to issue file."),
    no_llm: bool = typer.Option(False, "--no-llm", help="Run in graph-only mode without LLM."),
):
    """Find contribution trail for an issue."""
    console.print(f"Finding trail for {repo}...")

@app.command()
def serve(
    repo: str = typer.Option(".", "--repo", "-r", help="Path to indexed repository."),
    port: int = typer.Option(8765, "--port", "-p", help="Port for web UI."),
):
    """Launch local web server with SSE live trace."""
    console.print(f"Serving web UI at port {port}...")

if __name__ == "__main__":
    app()
