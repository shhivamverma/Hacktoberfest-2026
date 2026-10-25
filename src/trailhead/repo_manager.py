"""Repository manager: handles remote Git URLs, shallow caching, and automatic AST graph indexing."""
import ast
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from trailhead.config import EDGE_WEIGHTS

def is_remote_git_url(repo_input: str) -> bool:
    """Check if repository input string is a remote Git URL or GitHub/GitLab shorthand."""
    if not repo_input or not isinstance(repo_input, str):
        return False
    clean = repo_input.strip()
    if clean.startswith(("http://", "https://", "git@", "ssh://")):
        return True
    if clean.startswith(("github.com/", "gitlab.com/")):
        return True
    if clean.endswith(".git"):
        return True
    return False

def get_cache_root() -> Path:
    """Return persistent directory for cached cloned repositories."""
    base = Path.cwd() / ".repos_cache"
    base.mkdir(parents=True, exist_ok=True)
    return base

def clone_remote_repo(
    repo_url: str,
    on_event: Optional[Callable[[str, Any], None]] = None,
) -> Path:
    """Clone a remote Git repository into local cache with shallow depth."""
    clean_url = repo_url.strip()
    if clean_url.startswith("github.com/"):
        clean_url = "https://" + clean_url
    elif clean_url.startswith("gitlab.com/"):
        clean_url = "https://" + clean_url

    # Generate safe folder name: e.g. shhivamverma_Fetchathon-3.0
    safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", clean_url.split("//")[-1].replace(".git", ""))
    safe_name = safe_name.replace("github.com_", "").replace("gitlab.com_", "").strip("_")
    if not safe_name:
        safe_name = f"repo_{int(time.time())}"

    target_dir = get_cache_root() / safe_name

    # If already cloned and contains .git, reuse
    if target_dir.exists() and (target_dir / ".git").exists():
        if on_event:
            on_event("tool_call", {
                "name": "git.cache",
                "result_summary": f"Found cached repository: {safe_name}",
                "ms": 1,
            })
        return target_dir

    if on_event:
        on_event("tool_call", {
            "name": "git.clone",
            "result_summary": f"Cloning {clean_url} into local cache...",
            "ms": 0,
        })

    t0 = time.time()
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", clean_url, str(target_dir)],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        err = e.stderr.strip() or e.stdout.strip() or str(e)
        raise RuntimeError(f"Failed to clone git repository '{clean_url}': {err}")
    except Exception as e:
        raise RuntimeError(f"Error cloning repository '{clean_url}': {str(e)}")

    elapsed_ms = int((time.time() - t0) * 1000)
    if on_event:
        on_event("tool_call", {
            "name": "git.clone",
            "result_summary": f"Successfully cloned {safe_name} ({elapsed_ms}ms)",
            "ms": elapsed_ms,
        })

    return target_dir

def build_ast_graph(
    repo_dir: Path,
    on_event: Optional[Callable[[str, Any], None]] = None,
) -> Path:
    """Built-in pure-Python AST graph indexer.
    
    Extracts functions, classes, calls, inheritance, imports, and containment
    into a Graphify-compatible graph.json with zero external CLI dependencies.
    """
    t0 = time.time()
    out_dir = repo_dir / "graphify-out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "graph.json"

    # Find all Python files excluding build and virtualenv folders
    ignored_parts = {
        ".git", "__pycache__", ".venv", "venv", "env", "node_modules",
        ".pytest_cache", ".tox", "build", "dist", ".mypy_cache"
    }

    py_files: List[Path] = []
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in ignored_parts]
        for f in files:
            if f.endswith(".py"):
                py_files.append(Path(root) / f)

    nodes: List[Dict[str, Any]] = []
    links: List[Dict[str, Any]] = []

    # Symbol lookup table: symbol_name -> list of node_ids
    symbol_to_nodes: Dict[str, List[str]] = {}
    known_node_ids: Set[str] = set()

    def sanitize_id(s: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]", "_", s).lower().strip("_")

    # Pass 1: Extract Class and Function nodes
    for file_path in py_files:
        try:
            rel_file = str(file_path.relative_to(repo_dir)).replace("\\", "/")
        except ValueError:
            rel_file = file_path.name

        base_id = sanitize_id(rel_file.replace(".py", ""))

        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=rel_file)
        except Exception:
            continue

        for item in tree.body:
            if isinstance(item, ast.ClassDef):
                cls_name = item.name
                cls_id = f"{base_id}_{sanitize_id(cls_name)}"
                if cls_id not in known_node_ids:
                    known_node_ids.add(cls_id)
                    node_data = {
                        "id": cls_id,
                        "label": cls_name,
                        "_callable": True,
                        "_callable_class": True,
                        "_origin": "ast",
                        "community": 0,
                        "community_name": "Community 0",
                        "file_type": "code",
                        "norm_label": cls_name.lower(),
                        "source_file": rel_file,
                        "source_location": f"L{item.lineno}",
                    }
                    nodes.append(node_data)
                    symbol_to_nodes.setdefault(cls_name, []).append(cls_id)
                    symbol_to_nodes.setdefault(cls_name.lower(), []).append(cls_id)

                # Inner methods of class
                for sub in item.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_name = sub.name
                        method_id = f"{cls_id}_{sanitize_id(method_name)}"
                        if method_id not in known_node_ids:
                            known_node_ids.add(method_id)
                            nodes.append({
                                "id": method_id,
                                "label": f".{method_name}()",
                                "_callable": True,
                                "_origin": "ast",
                                "community": 0,
                                "community_name": "Community 0",
                                "file_type": "code",
                                "norm_label": f".{method_name}()",
                                "source_file": rel_file,
                                "source_location": f"L{sub.lineno}",
                            })
                            symbol_to_nodes.setdefault(method_name, []).append(method_id)
                            # Containment edge
                            links.append({
                                "source": cls_id,
                                "target": method_id,
                                "relation": "contains",
                                "weight": EDGE_WEIGHTS.get("contains", 0.7),
                                "confidence": "EXTRACTED",
                            })

            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_name = item.name
                func_id = f"{base_id}_{sanitize_id(func_name)}"
                if func_id not in known_node_ids:
                    known_node_ids.add(func_id)
                    nodes.append({
                        "id": func_id,
                        "label": f"{func_name}()",
                        "_callable": True,
                        "_origin": "ast",
                        "community": 0,
                        "community_name": "Community 0",
                        "file_type": "code",
                        "norm_label": f"{func_name}()",
                        "source_file": rel_file,
                        "source_location": f"L{item.lineno}",
                    })
                    symbol_to_nodes.setdefault(func_name, []).append(func_id)
                    symbol_to_nodes.setdefault(func_name.lower(), []).append(func_id)

    # Pass 2: Extract Calls, Inheritance, and Imports relationships
    for file_path in py_files:
        try:
            rel_file = str(file_path.relative_to(repo_dir)).replace("\\", "/")
        except ValueError:
            rel_file = file_path.name
        base_id = sanitize_id(rel_file.replace(".py", ""))

        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=rel_file)
        except Exception:
            continue

        for item in tree.body:
            if isinstance(item, ast.ClassDef):
                cls_id = f"{base_id}_{sanitize_id(item.name)}"
                # Base class inheritance
                for base in item.bases:
                    base_name = getattr(base, "id", None) or getattr(base, "attr", None)
                    if base_name and base_name in symbol_to_nodes:
                        for target_id in symbol_to_nodes[base_name]:
                            if target_id != cls_id:
                                links.append({
                                    "source": cls_id,
                                    "target": target_id,
                                    "relation": "inherits",
                                    "weight": EDGE_WEIGHTS.get("inherits", 0.8),
                                    "confidence": "EXTRACTED",
                                })

                # Class methods calls
                for sub in item.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_id = f"{cls_id}_{sanitize_id(sub.name)}"
                        for call_node in ast.walk(sub):
                            if isinstance(call_node, ast.Call):
                                callee_name = getattr(call_node.func, "id", None) or getattr(call_node.func, "attr", None)
                                if callee_name and callee_name in symbol_to_nodes:
                                    for target_id in symbol_to_nodes[callee_name][:2]:
                                        if target_id != method_id:
                                            links.append({
                                                "source": method_id,
                                                "target": target_id,
                                                "relation": "calls",
                                                "weight": EDGE_WEIGHTS.get("calls", 1.0),
                                                "confidence": "EXTRACTED",
                                            })

            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_id = f"{base_id}_{sanitize_id(item.name)}"
                for call_node in ast.walk(item):
                    if isinstance(call_node, ast.Call):
                        callee_name = getattr(call_node.func, "id", None) or getattr(call_node.func, "attr", None)
                        if callee_name and callee_name in symbol_to_nodes:
                            for target_id in symbol_to_nodes[callee_name][:2]:
                                if target_id != func_id:
                                    links.append({
                                        "source": func_id,
                                        "target": target_id,
                                        "relation": "calls",
                                        "weight": EDGE_WEIGHTS.get("calls", 1.0),
                                        "confidence": "EXTRACTED",
                                    })

    # Save graph.json
    graph_data = {
        "directed": False,
        "multigraph": False,
        "graph": {"schema_version": 1, "graphify_version": "0.9.95"},
        "nodes": nodes,
        "links": links,
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=2)

    # Write placeholder visual graph.html
    html_file = out_dir / "graph.html"
    if not html_file.exists():
        html_file.write_text(
            f"<!DOCTYPE html><html><head><title>AST Code Graph</title></head>"
            f"<body><h1>AST Graph for {repo_dir.name}</h1><p>{len(nodes)} code nodes, {len(links)} edges extracted.</p></body></html>",
            encoding="utf-8",
        )

    elapsed_ms = int((time.time() - t0) * 1000)
    if on_event:
        on_event("tool_call", {
            "name": "ast.index",
            "result_summary": f"Indexed {len(nodes)} nodes, {len(links)} edges in {elapsed_ms}ms",
            "ms": elapsed_ms,
        })

    return out_json

def ensure_repo_indexed(
    repo_dir: Path,
    on_event: Optional[Callable[[str, Any], None]] = None,
) -> Path:
    """Verify graphify-out/graph.json exists; automatically index if missing."""
    graph_json = repo_dir / "graphify-out" / "graph.json"
    if graph_json.exists():
        return graph_json

    if on_event:
        on_event("tool_call", {
            "name": "graph.index",
            "result_summary": f"Missing graph.json in {repo_dir.name}; initiating automatic indexing...",
            "ms": 0,
        })

    # Try Graphify CLI if installed
    graphify_bin = shutil.which("graphify")
    if not graphify_bin:
        win_local = Path(os.path.expanduser("~")) / ".local" / "bin" / "graphify.exe"
        if win_local.exists():
            graphify_bin = str(win_local)

    if graphify_bin:
        try:
            t0 = time.time()
            subprocess.run([graphify_bin, "extract", str(repo_dir), "--code-only"], check=True, timeout=60)
            if graph_json.exists():
                elapsed = int((time.time() - t0) * 1000)
                if on_event:
                    on_event("tool_call", {
                        "name": "graphify.extract",
                        "result_summary": f"Indexed using Graphify CLI ({elapsed}ms)",
                        "ms": elapsed,
                    })
                return graph_json
        except Exception:
            pass

    # Fallback to high-performance built-in pure Python AST indexer
    return build_ast_graph(repo_dir, on_event=on_event)

def resolve_repository(
    repo_input: Union[str, Path],
    on_event: Optional[Callable[[str, Any], None]] = None,
) -> Path:
    """Resolve repository input (local path or remote git URL) and ensure it is indexed."""
    input_str = str(repo_input).strip()
    if is_remote_git_url(input_str):
        repo_dir = clone_remote_repo(input_str, on_event=on_event)
    else:
        repo_dir = Path(input_str).resolve()
        if not repo_dir.exists():
            raise FileNotFoundError(f"Local repository path '{input_str}' does not exist on disk.")

    ensure_repo_indexed(repo_dir, on_event=on_event)
    return repo_dir
