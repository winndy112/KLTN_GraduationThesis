from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import httpx
import asyncio
from app.database.mongo import db_ioc

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])

class LogEntry(BaseModel):
    ts: float
    # Allow other fields dynamically
    class Config:
        extra = "allow"

class AggregatedLogResponse(BaseModel):
    data: List[Dict[str, Any]]
    next_cursor: float

async def fetch_logs_from_sensor(client: httpx.AsyncClient, sensor: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Fetches logs from a single sensor.
    """
    ip = sensor.get("ip_mgmt")
    if not ip:
        return []
    
    # Assuming sensor runs on port 8001 as per our design
    # In production, port might be stored in DB or config
    url = f"http://{ip}:8001/api/v1/logs/search"
    
    try:
        resp = await client.get(url, params=params, timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        logs = data.get("data", [])
        # Tag logs with sensor_id for UI
        for log in logs:
            log["_sensor_id"] = sensor.get("sensor_id")
            log["_sensor_hostname"] = sensor.get("hostname")
        return logs
    except Exception as e:
        print(f"Error fetching from {sensor.get('sensor_id')}: {e}")
        return []

@router.get("/query")
async def query_logs(
    mode: str = Query(..., regex="^(live|history)$"),
    start_ts: float = 0,
    end_ts: float = float('inf'),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    cursor: float = 0,
    sensor_ids: Optional[List[str]] = Query(None)
):
    """
    Aggregates logs from all (or specified) active sensors.
    """
    # 1. Get sensors
    query = {"status": "active"}
    if sensor_ids:
        query["sensor_id"] = {"$in": sensor_ids}
    
    sensors = list(db_ioc["sensor_infor"].find(query, {"sensor_id": 1, "ip_mgmt": 1, "hostname": 1}))
    
    if not sensors:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0, "next_cursor": cursor}

    # 2. Fan-out requests (fetch more than needed for accurate pagination)
    params = {
        "mode": mode,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "limit": page_size * 10,  # Fetch more to ensure we have enough after merge
        "cursor": cursor
    }
    
    async with httpx.AsyncClient() as client:
        tasks = [fetch_logs_from_sensor(client, s, params) for s in sensors]
        results = await asyncio.gather(*tasks)
    
    # 3. Merge and Sort
    all_logs = []
    for res in results:
        all_logs.extend(res)
    
    # Sort by ts descending (newest first)
    all_logs.sort(key=lambda x: x.get("ts", 0), reverse=True)
    
    # Apply pagination
    total = len(all_logs)
    skip = (page - 1) * page_size
    sliced_logs = all_logs[skip:skip + page_size]
    
    # Calculate next cursor (max ts seen in this batch)
    next_cursor = cursor
    if sliced_logs:
        max_ts = max(l.get("ts", 0) for l in sliced_logs)
        next_cursor = max(cursor, max_ts)


    return {
        "items": sliced_logs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        "next_cursor": next_cursor
    }

