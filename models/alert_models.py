from pydantic import BaseModel, IPvAnyAddress, Field
from typing import Optional, Dict, List
import datetime

class AlertSrcDst(BaseModel):
    ip: str
    port: Optional[int] = None
    netmask: Optional[str] = None

class Alert(BaseModel):
    ts: str
    sensor_id: str
    rule_id: str
    priority: int
    classification: str
    action: str
    msg: str
    proto: str
    pkt_num: int
    pkt_gen: str
    dir: str
    src: AlertSrcDst
    dst: AlertSrcDst
    b64_data: Optional[str] = None
    mitre: Optional[str] = None
    rule_version: Optional[str] = None
    correlation_id: Optional[str] = None

class ProcessorAlert(BaseModel):
    sensor_id: str
    timestamp: datetime.datetime

    src_ip: Optional[IPvAnyAddress] = None
    src_port: Optional[int] = None
    dst_ip: Optional[IPvAnyAddress] = None
    dst_port: Optional[int] = None
    protocol: Optional[str] = None

    rule_id: str
    rule_name: str

    type: str = Field("zeek_processor", description="Alert source type")
    severity: str
    category: str
    log_type: str

    message: str
    mitre_techniques: List[str] = []
    tags: List[str] = []

    source: Optional[str] = None
    uid: Optional[str] = None
    raw: Optional[dict] = None