"""Local Ollama LLM and embedding client with defensive tag stripping and retry logic."""
import json
import re
from typing import Any, Dict, List, Optional, Union

import httpx

from trailhead.config import (
    EMBED_MODEL,
    LLM_RETRIES,
    LLM_TIMEOUT_S,
    MODEL_MAIN,
    NUM_CTX,
    NUM_PREDICT,
    OLLAMA_HOST,
    SEED,
    TEMPERATURE,
)

def strip_tags(text: str) -> str:
    """Defensively strip <think>...</think>, </think>, and tool call tags from model output."""
    if not text:
        return ""
    # Strip <think>...</think> blocks
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip any stray opening/closing think tags
    cleaned = re.sub(r"</?think>", "", cleaned)
    # Strip tool call tags
    cleaned = re.sub(r"<tool_call>.*?</tool_call>", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"</?tool_call>", "", cleaned)
    return cleaned.strip()

def extract_json_object(text: str) -> str:
    """Extract clean JSON string from text that may contain markdown or formatting."""
    cleaned = strip_tags(text).strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2 and lines[-1].startswith("```"):
            cleaned = "\n".join(lines[1:-1]).strip()
    return cleaned

def chat(
    messages: List[Dict[str, str]],
    schema: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    host: Optional[str] = None,
    temperature: float = TEMPERATURE,
    seed: int = SEED,
    timeout: float = LLM_TIMEOUT_S,
    retries: int = LLM_RETRIES,
) -> Dict[str, Any]:
    """Execute chat completion request to local Ollama instance with schema and retries."""
    active_host = host or OLLAMA_HOST
    active_model = model or MODEL_MAIN

    payload: Dict[str, Any] = {
        "model": active_model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
            "seed": seed,
            "temperature": temperature,
        },
    }

    if schema:
        payload["format"] = schema

    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                res = client.post(f"{active_host}/api/chat", json=payload)
                res.raise_for_status()
                data = res.json()

            raw_content = data.get("message", {}).get("content", "")
            clean = extract_json_object(raw_content)

            eval_count = data.get("eval_count", 0)
            eval_duration = data.get("eval_duration", 0)
            tok_s = (eval_count / (eval_duration / 1e9)) if eval_duration > 0 else 0.0

            # If schema was requested, validate JSON parseability
            if schema:
                json.loads(clean)

            return {
                "content": clean,
                "raw_content": raw_content,
                "eval_count": eval_count,
                "eval_duration": eval_duration,
                "tokens_per_sec": tok_s,
                "prompt_eval_count": data.get("prompt_eval_count", 0),
            }
        except Exception as e:
            last_error = e
            if attempt < retries:
                # Retry once with stricter prompt instruction and temperature 0
                payload["options"]["temperature"] = 0.0
                if messages and messages[-1].get("role") == "user":
                    payload["messages"] = list(messages) + [
                        {"role": "user", "content": "Return only valid JSON matching the requested schema."}
                    ]

    raise RuntimeError(f"Ollama chat failed after {retries + 1} attempts: {last_error}")

def embed(
    texts: Union[str, List[str]],
    model: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = 30.0,
) -> List[List[float]]:
    """Generate dense embeddings using local nomic-embed-text model."""
    active_host = host or OLLAMA_HOST
    active_model = model or EMBED_MODEL
    inputs = [texts] if isinstance(texts, str) else texts

    payload = {"model": active_model, "input": inputs}
    with httpx.Client(timeout=timeout) as client:
        res = client.post(f"{active_host}/api/embed", json=payload)
        res.raise_for_status()
        data = res.json()
        return data.get("embeddings", [])
