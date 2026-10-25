"""Command-line interface for Trailhead."""
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
import typer
from rich.console import Console
from rich.table import Table

from trailhead.config import OLLAMA_HOST
from trailhead.graphio import load_graph
from trailhead.netguard import get_blocked_attempts, install_netguard
from trailhead.repo_manager import resolve_repository
from trailhead.retrieve import retrieve_nodes
from trailhead.textproc import extract_hints

app = typer.Typer(help="Trailhead: Offline issue-to-code trail finder for open-source contributors.")
console = Console(legacy_windows=False)

def get_graphify_bin() -> str:
    """Find path to Graphify executable."""
    candidate = shutil.which("graphify")
    if not candidate:
        win_local = Path(os.path.expanduser("~")) / ".local" / "bin" / "graphify.exe"
        if win_local.exists():
            candidate = str(win_local)
    return candidate or "graphify"

def get_graphify_version() -> str:
    """Return installed Graphify CLI version."""
    candidate = get_graphify_bin()
    try:
        res = subprocess.run([candidate, "--version"], capture_output=True, text=True, timeout=5)
        out = res.stdout.strip() or res.stderr.strip()
        return out.split()[-1] if out else "installed"
    except Exception:
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
    """Index a repository using Graphify extract, cluster-only and export html."""
    install_netguard()
    graphify_bin = get_graphify_bin()
    target_repo = Path(repo).resolve()

    if not target_repo.exists():
        console.print(f"[bold red]Error: repository path '{repo}' does not exist.[/bold red]")
        raise typer.Exit(code=1)

    console.print(f"[bold cyan]1. Extracting code AST graph with Graphify...[/bold cyan]")
    t0 = time.time()
    subprocess.run([graphify_bin, "extract", str(target_repo), "--code-only"], check=True)
    t_extract = time.time() - t0

    console.print(f"[bold cyan]2. Running cluster-only analysis...[/bold cyan]")
    try:
        subprocess.run([graphify_bin, "cluster-only", str(target_repo), "--no-label"], check=False)
    except Exception:
        pass

    console.print(f"[bold cyan]3. Exporting visual graph.html...[/bold cyan]")
    try:
        subprocess.run([graphify_bin, "export", "html"], cwd=str(target_repo), check=False)
    except Exception:
        pass

    out_json = target_repo / "graphify-out" / "graph.json"
    console.print(f"[bold green][OK] Index complete in {t_extract:.2f}s! Graph saved to {out_json}[/bold green]")

@app.command()
def trail(
    repo: str = typer.Option(".", "--repo", "-r", help="Path to indexed repository."),
    issue: str = typer.Option(..., "--issue", "-i", help="Issue text, path to issue file, or '-' for stdin."),
    no_llm: bool = typer.Option(False, "--no-llm", help="Run in graph-only mode without LLM."),
):
    # 1. Resolve repository & index
    try:
        repo_path = resolve_repository(repo)
    except Exception as e:
        console.print(f"[bold red]Error resolving repository '{repo}': {e}[/bold red]")
        raise typer.Exit(code=1)

    install_netguard()
    
    # 2. Resolve issue text
    if issue == "-":
        issue_text = sys.stdin.read()
    elif Path(issue).exists() and Path(issue).is_file():
        issue_text = Path(issue).read_text(encoding="utf-8", errors="replace")
    else:
        issue_text = issue

    # 3. Locate graph.json
    graph_path = repo_path / "graphify-out" / "graph.json"
    if not graph_path.exists():
        console.print(f"[bold red]Error: graph.json not found at {graph_path}. Run 'trailhead index {repo}' first.[/bold red]")
        raise typer.Exit(code=1)

    nodes, edges = load_graph(graph_path, repo_root=repo_path)
    hints = extract_hints(issue_text)
    scores = retrieve_nodes(nodes, issue_text, hints=hints)

    # Filter to code nodes with positive scores
    ranked_nodes = sorted(
        [n for n in nodes if n.kind in ("function", "class") and scores.get(n.id, 0.0) > 0.0],
        key=lambda n: scores.get(n.id, 0.0),
        reverse=True,
    )

    # Print markdown table
    print("\n# Trailhead Contribution Trail (No-LLM Retrieval Mode)\n")
    print(f"**Repository**: `{repo_path.name}` | **Identified Hints**: {len(hints)}\n")
    print("| Rank | Target Function / Symbol | File | Lines | BM25 Score |")
    print("|:---|:---|:---|:---|:---|")
    for rank, node in enumerate(ranked_nodes[:10], start=1):
        lines_str = f"L{node.start}-{node.end}" if node.start and node.end else "file-level"
        print(f"| {rank} | `{node.label}` | `{node.file}` | {lines_str} | {scores.get(node.id, 0.0):.3f} |")
    print()

@app.command()
def serve(
    repo: str = typer.Option(".", "--repo", "-r", help="Path to indexed repository."),
    port: int = typer.Option(8765, "--port", "-p", help="Port for web UI."),
):
    """Launch local web server with SSE live trace."""
    import uvicorn
    console.print(f"[bold green]Starting Trailhead Web UI on http://127.0.0.1:{port}[/bold green]")
    uvicorn.run("trailhead.server:app", host="127.0.0.1", port=port, log_level="info")

if __name__ == "__main__":
    app()

