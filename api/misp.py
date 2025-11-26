from __future__ import annotations
import os, uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from app.database.mongo import db_ioc
from app.services.misp_service import MISPService
from app.api.helpers import _admin_auth

router = APIRouter(prefix="/api/v1/misp", tags=["misp"])
def _svc() -> MISPService:
    return MISPService(db_ioc)

def _rid(x_request_id: Optional[str] = Header(None)) -> str:
    return x_request_id or uuid.uuid4().hex[:8]
@router.get("/ping")
def misp_ping(_=Depends(_admin_auth), svc: MISPService = Depends(_svc)):
    return svc.ping()
@router.get("/stats")
def misp_stats(svc: MISPService = Depends(_svc)):
    return svc.stats()

@router.get("/events")
def list_events(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    event_id: Optional[str] = Query(None, description="Filter by event_id (exact match)"),
    svc: MISPService = Depends(_svc)
):
    q = {}
    if event_id:
        # User wants exact match, no regex.
        # Try to convert to int, as DB stores event_id as int.
        try:
            eid_int = int(event_id.strip())
            q["event_id"] = eid_int
        except ValueError:
            # If input is not an integer (e.g. "abc"), it won't match any event_id (which are ints).
            # We can return empty list immediately or let query fail.
            # Let's force a query that returns nothing.
            q["event_id"] = -1

    total = svc.count_events(q)
    skip = (page - 1) * page_size
    docs = svc.query_events(q, skip=skip, limit=page_size)
    for d in docs: d.pop("_id", None)
    
    return {
        "items": docs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.get("/iocs")
def list_iocs(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    svc: MISPService = Depends(_svc)
):
    q = {}
    total = svc.count_iocs(q)
    skip = (page - 1) * page_size
    docs = svc.query_iocs(q, skip=skip, limit=page_size)
    for d in docs: d.pop("_id", None)
    
    return {
        "items": docs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


# Pull ngay (24h, exclude_imported=True)
@router.post("/pull/now")
def pull_now(_=Depends(_admin_auth), rid: str = Depends(_rid), svc: MISPService = Depends(_svc)):
    try:
        res = svc.pull(since="24h", exclude_imported=True, request_id=rid)
        return {"request_id": rid, **res}
    except Exception as e:
        raise HTTPException(500, f"pull error: {e}")

# Pull tuỳ biến nếu cần
@router.post("/pull")
def pull_custom(
    since: str = Query("24h"),
    published: Optional[bool] = Query(None),
    exclude_imported: bool = Query(True),
    _=Depends(_admin_auth),
    rid: str = Depends(_rid),
    svc: MISPService = Depends(_svc),
):
    try:
        res = svc.pull(since=since, published=published, exclude_imported=exclude_imported, request_id=rid)
        return {"request_id": rid, **res}
    except Exception as e:
        raise HTTPException(500, f"pull error: {e}")

@router.post("/tag")
def tag_event(
    event_uuid: str = Query(...),
    tag: str = Query(...),
    action: str = Query("add", regex="^(add|remove)$"),
    local: bool = Query(True),
    _=Depends(_admin_auth),
    svc: MISPService = Depends(_svc),
):
    res = svc.tag_event(event_uuid, tag, add=(action=="add"), local=local)
    if not res.get("ok"): raise HTTPException(500, res.get("error","tag error"))
    return res
