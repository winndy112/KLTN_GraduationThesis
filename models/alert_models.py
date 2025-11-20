from pydantic import BaseModel
from typing import Optional, Dict

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