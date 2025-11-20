from typing import Optional, Any, List, Dict, Literal
import re, os, datetime
from bson import ObjectId
from fastapi import APIRouter, Path, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


from app.services.rule_set_builder import build_files_for_rule_set
from app.services.rule_set_deploy import deploy_rule_set_version
from app.services.rules_service import build_rules_for_event, build_rules_for_all_new
from app.database.collections import (
    col_rule_items, col_rule_sets, col_rule_set_items, col_iocs, col_events, col_sensor_infor
)
from app.models.rule_models import RuleItem, RuleSetBuildResponse
RULE_ENGINE = os.getenv("RULE_ENGINE", "snort3")

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])

# YYYY.MM.DD-HHMMSS-e<event_id>[-NN]
VERSION_RE = r"^\d{4}\.\d{2}\.\d{2}-\d{6}-e\d+(?:-\d{2})?$"


def _ensure_event_id_exists(eid: int) -> None:
    exists = (
        col_iocs.count_documents({"event_id": int(eid)}, limit=1) or
        col_events.count_documents({"event_id": int(eid)}, limit=1)
    )
    if not exists:
        raise HTTPException(status_code=400, detail=f"event_id={eid} is not present in database")


@router.post("/convert")
async def convert_rules(
    event_id: Optional[int] = Query(default=None, ge=1, description="If omitted: convert all events")
):
    """
    Convert các IoC sang Rules item
    - event_id=int(): nhỏ nhất là 1, phải có mặt trong danh sách event
    - event_id=empty: convert all event
    """
    if event_id is None:
        return {"ok": True, "results": build_rules_for_all_new()}
    _ensure_event_id_exists(event_id)
    return {"ok": True, **build_rules_for_event(event_id)}

@router.get("/items", response_model=List[RuleItem])
async def list_rule_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    ioc_type: Optional[str] = Query(None, description="Lọc theo loại IOC"),
    keyword: Optional[str] = Query(None, description="Tìm theo keyword"),
):
    """
    Liệt kê rule documents trong rule_items 
    - Lọc theo ioc type hoặc bỏ trống
    - Lọc theo keyword hoặc bỏ trống
    """
    query: Dict[str, Any] = {"doc_type": "item"}

    if ioc_type:
        query["metadata.ioc_type"] = ioc_type

    if keyword:
        regex = {"$regex": keyword, "$options": "i"}
        query["$or"] = [
            {"msg": regex},
            {"rule": regex},
            {"metadata.ioc_type": regex},
            # thêm field khác nếu cần
        ]

    cursor = (
        col_rule_items
        .find(query)
        .skip(skip)
        .limit(limit)
        .sort("sid", 1)
    )

    items = [RuleItem(**{**doc, "id": str(doc["_id"])}) for doc in cursor]
    return items


@router.get("/sets")
async def list_rule_sets(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500)
):
    """
    Liệt kê danh sách rule sets đã có
    """
    sets = list(
        col_rule_sets.find(
            {},
            {"_id": 1, "name": 1, "version": 1, "event_id": 1, "item_count": 1, "status": 1}
        ).skip(skip).limit(limit)
    )
    for s in sets:
        s["_id"] = str(s["_id"])
    return {"sets": sets, "skip": skip, "limit": limit}


@router.get("/sets/{version}/items")
async def list_items_by_version(
    version: str = Path(..., description="Rule set version, e.g. 2025.11.15-112233-e1"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):

    """
    Liệt kê rule items theo set_version, bắt buộc nhập rule set version
    """
    if not re.match(VERSION_RE, version):
        raise HTTPException(status_code=400, detail="Invalid version format")

    links = list(
        col_rule_set_items.find({"set_version": version}, {"item_id": 1, "_id": 0})
        .skip(skip).limit(limit)
    )
    item_ids = [d["item_id"] for d in links if d.get("item_id")]
    if not item_ids:
        return {"version": version, "total": 0, "skip": skip, "limit": limit, "items": []}

    oids = [ObjectId(x) for x in item_ids if ObjectId.is_valid(x)]
    if not oids:
        return {"version": version, "total": 0, "skip": skip, "limit": limit, "items": []}

    cur = col_rule_items.find(
        {"_id": {"$in": oids}},
        {"_id": 1, "sid": 1, "msg": 1, "current_rev": 1, "rule_hash": 1, "rule_text": 1}
    )
    items = list(cur)
    for d in items:
        d["_id"] = str(d["_id"])

    total = col_rule_set_items.count_documents({"set_version": version})
    return {"version": version, "total": total, "skip": skip, "limit": limit, "items": items}

#---------------------------------------------------------------
from app.models.converted_tag_models import ConvertedTagRequest
from app.services.converted_tag_service import toggle_converted_tag

@router.post("/converted-tag")
async def api_toggle_converted_tag(body: ConvertedTagRequest):
    """
    Tag / untag 'console:converted' trên các IOC tương ứng:

    - scope='all'   : toàn bộ IOC
    - scope='event' : các IOC thuộc event_id
    - scope='sid'   : các IOC gắn với rule sid cho trước
    """
    return toggle_converted_tag(body)
#---------------------------------------------------------------

@router.post("/{rule_set_version}/build", response_model=RuleSetBuildResponse)
async def api_build_rule_set(
    rule_set_version: str = Path(..., description="Rule set version, e.g. 2025.11.15-080816-e1")
):
    """
    tạo file .tgz + update rule_sets.
    """
    try:
        rs = build_files_for_rule_set(rule_set_version)
    except ValueError:
        raise HTTPException(status_code=404, detail="rule_set not found")

    tar_info = (rs.get("files") or {}).get("tar") or {}
    return RuleSetBuildResponse(
        id=str(rs["_id"]),
        version=rs["version"],
        build_time=rs["build_time"].isoformat(),
        path=tar_info.get("path", ""),
        sha256=tar_info.get("sha256", ""),
        item_count=rs.get("item_count", 0),
        status=rs.get("status", "ready"),
        active=rs.get("active", False),
    )
# ---------- /{version}/deploy ----------

class RuleSetDeployRequest(BaseModel):
    target: Literal["all", "list"] = Field(
        "all", description="all sensors or only specific list"
    )
    sensors: Optional[List[str]] = Field(
        default=None, description="list sensor_id when target='list'"
    )


class RuleSetDeployResponse(BaseModel):
    rule_set_version: str
    matched_sensors: int
    modified_sensors: int


@router.post("/{rule_set_version}/deploy", response_model=RuleSetDeployResponse)
async def api_deploy_rule_set(
    rule_set_version: str = Path(..., description="Rule set version, vd: 2025.11.15-080816-e1"),
    body: RuleSetDeployRequest = ...,
):
    """
    Deploy rule_set theo version:
    - Đánh dấu active cho rule_set đó
    - Append version vào desired_rule_versions của sensor_infor
    """
    try:
        res = deploy_rule_set_version(
            rule_set_version,
            target=body.target,
            sensors=body.sensors,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="rule_set not found")
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RuleSetDeployResponse(**res)

# ---------- /{version}/file cho sensor pull ----------
@router.get("/{version}/file")
async def api_download_rule_file(version: str):
    """
    API cho phép sensor pull file rules về
    """
    rs = col_rule_sets.find_one({"version": version})
    if not rs:
        raise HTTPException(status_code=404, detail="rule_set not found")

    tar_info = (rs.get("files") or {}).get("tar") or {}
    path = tar_info.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="rule_set not built yet")

    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=f"{rs.get('engine', RULE_ENGINE)}_{version}.tgz",
        headers={
            "X-Rule-Version": version,
        },
    )