from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, constr, validator

class Heartbeat(BaseModel):
    sensor_id: str
    status: str = Field("active", pattern=r"^(?i)(active|inactive)$")
    hostname: str
    roles: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    ip_mgmt: Optional[str] = None
    ifaces: List[str] = Field(default_factory=list)
    engine_versions: Dict[str, Any] = Field(default_factory=dict)
    enrolled_at: Optional[str] = None
    auth: Dict[str, Any] = Field(default_factory=dict)

    # ==== metrics ====
    last_heartbeat: str
    cpu_pct: float
    mem_pct: float
    disk_free_gb: float
    traffic: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    alerts_window: Optional[Dict[str, Any]] = None
    # ==== intervals ====

    heartbeat_interval_s: Optional[int] = 10
    status_interval_s: Optional[int] = 60
    
    @validator("status", pre=True)
    def _normalize_status(cls, v): return "active"

class StatusUpdate(BaseModel):
    sensor_id: str
    status: str = Field("active", pattern=r"^(?i)(active|inactive)$")
    # NEW: thông tin rule trên sensor
    rule_version: Optional[str] = None          # version mới nhất
    rule_versions: List[str] = Field(default_factory=list)  # list các set đã cài