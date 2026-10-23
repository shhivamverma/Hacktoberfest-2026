"""Tests for Phase 1: LLM client, tag stripping, and CLI doctor command."""
import json
from pathlib import Path
import pytest
from typer.testing import CliRunner

from trailhead.cli import app
from trailhead.config import MODEL_FAST
from trailhead.llm import chat, strip_tags, extract_json_object

runner = CliRunner()

def test_llm_strips_leaked_tags():
    # Test stripping leading/closing tags
    raw1 = '</think>{"a":1}'
    assert extract_json_object(raw1) == '{"a":1}'
    assert json.loads(extract_json_object(raw1)) == {"a": 1}

    # Test stripping complete think block
    raw2 = '<think>I should output a=1</think>{"a":1}'
    assert extract_json_object(raw2) == '{"a":1}'

    # Test stripping markdown json code fences
    raw3 = '```json\n{"a":1}\n```'
    assert extract_json_object(raw3) == '{"a":1}'

    # Test tool call stripping
    raw4 = '<tool_call>call()</tool_call>{"a":1}'
    assert extract_json_object(raw4) == '{"a":1}'

@pytest.mark.ollama
def test_llm_smoke():
    schema = {
        "type": "object",
        "properties": {
            "answer": {"type": "string", "enum": ["yes", "no"]}
        },
        "required": ["answer"]
    }
    messages = [
        {"role": "user", "content": "Is water wet? Answer using the JSON schema."}
    ]
    # Use MODEL_FAST for rapid testing
    res = chat(messages=messages, schema=schema, model=MODEL_FAST, timeout=30.0)
    
    assert "content" in res
    assert "<think>" not in res["content"]
    assert "</think>" not in res["content"]
    assert res["tokens_per_sec"] > 0
    
    data = json.loads(res["content"])
    assert data.get("answer") in ("yes", "no")

def test_doctor_writes_json(tmp_path):
    env_file = tmp_path / "RUN_ENV.json"
    result = runner.invoke(app, ["doctor", "--out", str(env_file)])
    assert result.exit_code == 0
    assert env_file.exists()

    with open(env_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "os" in data
    assert "cpu" in data
    assert "ram_gb" in data
    assert isinstance(data["ram_gb"], (int, float))
    assert "models" in data
    assert isinstance(data["models"], list)
    assert "graphify_version" in data
    assert data["external_apis"] == []
