"""Data contracts and Pydantic models for Trailhead."""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

class Node(BaseModel):
    id: str
    label: str
    kind: Literal["function", "class", "file", "other"] = "other"
    file: str = ""
    start: Optional[int] = None
    end: Optional[int] = None
    text: str = ""
    community: int = 0

class Edge(BaseModel):
    src: str
    dst: str
    relation: str = "other"
    confidence: str = "EXTRACTED"
    weight: float = 1.0

class Hint(BaseModel):
    kind: Literal["trace", "identifier", "error", "path"]
    value: str
    file: Optional[str] = None
    line: Optional[int] = None
    func: Optional[str] = None

class Candidate(BaseModel):
    alias: str  # e.g. "C1"
    node_id: str
    score_retrieval: float = 0.0
    score_graph: float = 0.0
    score_fused: float = 0.0
    reason_path: str = ""

class Pick(BaseModel):
    alias: str
    node_id: str
    role: Literal["edit", "read_first"]
    why: str
    file: str
    start: Optional[int] = None
    end: Optional[int] = None
    snippet: str = ""
    level: Literal["span", "file"] = "span"

class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any] = Field(default_factory=dict)
    result_summary: str = ""
    ms: float = 0.0
    ok: bool = True

class Trail(BaseModel):
    status: Literal["ok", "low_confidence", "graph_only"]
    confidence: Literal["high", "medium", "low"] = "medium"
    edit: List[Pick] = Field(default_factory=list)
    read_first: List[Pick] = Field(default_factory=list)
    blast: List[Dict[str, Any]] = Field(default_factory=list)
    tests: List[str] = Field(default_factory=list)
    checklist: List[str] = Field(default_factory=list)
    explore_areas: List[str] = Field(default_factory=list)
    clarifying_question: Optional[str] = None
    trace: List[ToolCall] = Field(default_factory=list)
    timing: Dict[str, float] = Field(default_factory=dict)
    model: Dict[str, Any] = Field(default_factory=dict)
    netguard: Dict[str, Any] = Field(default_factory=lambda: {"blocked_attempts": 0})
