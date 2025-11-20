from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from datetime import datetime

# ===== Mongo docs =====
class RuleItem(BaseModel):
    doc_type: Literal["item"] = "item"
    gid: int = 1
    sid: int
    current_rev: int = 1
    msg: str
    classtype: str = "trojan-activity"
    priority: int = 1
    rule_text: str
    rule_hash: str
    protocol: str
    src_sel: str
    dst_sel: str
    buffers: List[Dict[str, Any]] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    flow: Dict[str, Any] = Field(default_factory=dict)
    flowbits: Dict[str, Any] = Field(default_factory=dict)
    references: List[Dict[str, str]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    mitre: List[Dict[str, Any]] = Field(default_factory=list)

class RuleSet(BaseModel):
    name: str                      # ví dụ: f"misp-event-{event_id}"
    version: str                   # ví dụ: YYYY.MM.DD-HHMMSS-e<event_id>[-NN]
    event_id: int
    event_uuid: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    item_count: int
    status: Literal["draft","ready","disabled"] = "draft"
    notes: Optional[str] = None

class RuleSetItem(BaseModel):
    set_id: str      # ObjectId as str (của rule_sets)
    item_id: str     # ObjectId as str (của rule_items)
    rev: int

class RuleSetBuildResponse(BaseModel):
    id: str
    version: str
    build_time: str
    path: str
    sha256: str
    item_count: int
    status: str
    active: bool