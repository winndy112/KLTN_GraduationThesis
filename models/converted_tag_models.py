from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, model_validator

class ConvertedTagScope(str, Enum):
    all = "all"
    event = "event"
    sid = "sid"

class ConvertedTagAction(str, Enum):
    tag = "tag"
    untag = "untag"

class ConvertedTagRequest(BaseModel):
    action: ConvertedTagAction                 # "tag" hoặc "untag"
    scope: ConvertedTagScope = ConvertedTagScope.all
    event_id: Optional[int] = None            # dùng khi scope = "event"
    sids: Optional[List[int]] = None          # dùng khi scope = "sid"
    tag: str = "console:converted"            # mặc định tag này

    @model_validator(mode="after")
    def validate_scope(self) -> "ConvertedTagRequest":
        if self.scope == ConvertedTagScope.event and self.event_id is None:
            raise ValueError("event_id is required when scope='event'")
        if self.scope == ConvertedTagScope.sid and not self.sids:
            raise ValueError("sids is required when scope='sid'")
        return self