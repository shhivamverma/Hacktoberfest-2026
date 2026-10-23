# Third-Party Licenses & Software Disclosures

Trailhead relies exclusively on open-weights models and permissive open-source tools. All inference and processing run strictly local and offline.

---

## 1. Local Open-Weights Models

### Qwen3 (4B & 1.7B)
- **Model Names**: `qwen3:4b`, `qwen3:1.7b`
- **Origin**: Alibaba Cloud / Qwen Team
- **License**: Apache License 2.0
- **License URL**: https://www.apache.org/licenses/LICENSE-2.0
- **Summary**: Permissive open-weights license permitting commercial and research local use with attribution.

### Nomic Embed Text
- **Model Name**: `nomic-embed-text` (v1.5)
- **Origin**: Nomic AI
- **License**: Apache License 2.0
- **License URL**: https://www.apache.org/licenses/LICENSE-2.0
- **Summary**: High-performance open-weights dense text embedding model.

---

## 2. Local Inference Runtime & Code Graph Tooling

### Ollama
- **Version**: 0.40.9+
- **License**: MIT License
- **License URL**: https://github.com/ollama/ollama/blob/main/LICENSE
- **Summary**: Lightweight local model runner listening strictly on `localhost:11434`.

### Graphify (`graphifyy`)
- **Version**: 0.9.95+
- **License**: MIT License
- **License URL**: https://github.com/Graphify-Labs/graphify/blob/main/LICENSE
- **Summary**: AST-based code-to-graph analysis and clustering tool.

---

## 3. Python Runtime Dependencies

| Library | License | Source / Repository |
|:---|:---|:---|
| **Pydantic** | MIT License | https://github.com/pydantic/pydantic |
| **NetworkX** | BSD 3-Clause License | https://github.com/networkx/networkx |
| **NumPy** | BSD 3-Clause License | https://github.com/numpy/numpy |
| **HTTPX** | BSD 3-Clause License | https://github.com/encode/httpx |
| **FastAPI** | MIT License | https://github.com/fastapi/fastapi |
| **Uvicorn** | BSD 3-Clause License | https://github.com/encode/uvicorn |
| **Typer** | MIT License | https://github.com/fastapi/typer |
| **Rich** | MIT License | https://github.com/Textualize/rich |
| **psutil** | BSD 3-Clause License | https://github.com/giampaolo/psutil |
| **pytest** | MIT License | https://github.com/pytest-dev/pytest |

---

## 4. Policy Compliance

- **Hosted AI APIs**: None. Zero external network calls or hosted inference APIs (OpenAI, Anthropic, Google, Cohere, etc.).
- **Network Access**: At runtime, all non-localhost sockets are intercepted and blocked by `netguard.py`.
