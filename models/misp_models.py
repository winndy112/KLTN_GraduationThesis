from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime

class GalaxyAttack(BaseModel):
    tactic: Optional[str] = None
    technique: Optional[str] = None
    external_id: Optional[str] = None
    platforms: Optional[List[str]] = None

class GalaxyItem(BaseModel):
    galaxy_type: Optional[str] = None
    galaxy_uuid: Optional[str] = None
    cluster_value: Optional[str] = None
    cluster_uuid: Optional[str] = None
    namespace: Optional[str] = "misp-galaxy"
    tag: Optional[str] = None
    meta: Optional[dict] = None
    attack: Optional[GalaxyAttack] = None

class EventOut(BaseModel):
    event_id: int
    uuid: str
    info: Optional[str] = None
    orgc: Optional[str] = None
    org: Optional[str] = None
    threat_level_id: Optional[int] = 4
    analysis: Optional[int] = 0
    distribution: Optional[int] = 0
    sharing_group_id: Optional[str] = None
    published: bool = False
    attribute_count: int = 0
    date: datetime
    timestamp: datetime
    tags: List[str] = Field(default_factory=list)
    galaxies: List[GalaxyItem] = Field(default_factory=list)

class IocOut(BaseModel):
    uuid: str
    event_uuid: str
    type: str
    value: str
    to_ids: bool = False
    category: Optional[str] = None
    comment: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    timestamp: datetime
    tags: List[str] = Field(default_factory=list)
    norm: dict
