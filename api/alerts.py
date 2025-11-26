from fastapi import APIRouter, HTTPException, Header, Query, Body
from app.models.alert_models import Alert
from datetime import datetime, timedelta
from typing import Optional, List, Any, Dict, Union
from bson import ObjectId
from app.database.mongo import db_sec
from app.api.helpers import _check_key, _normalize, _parse_ts 

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])
API_KEYS = {"sensor-1": "K1-very-secret", "sensor-2": "K2-very-secret"} 

        
@router.post("/push")
async def push_flex(
    body: Union[Dict[str, Any], List[Dict[str, Any]]] = Body(...),
    x_api_key: str = Header(None)
):
    # Chuẩn hóa về list
    alerts: List[Dict[str, Any]] = body if isinstance(body, list) else [body]
    if not alerts:
        return {"ok": True, "inserted": 0}

    # Xác thực theo sensor đầu tiên (nếu muốn chặt hơn, có thể loop kiểm tra từng cái)
    sid = alerts[0].get("sensor_id")
    _check_key(sid, x_api_key)

    # Normalize & insert
    docs = [_normalize(a) for a in alerts]
    # print(docs)
    try:
        res = db_sec.ids_alerts.insert_many(docs, ordered=False)
        return {"ok": True, "inserted": len(res.inserted_ids)}
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")



def _to_dict(doc: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(doc)
    d["_id"] = str(d["_id"])
    # gọn dữ liệu trả về
    d["src"] = doc.get("src", {})
    d["dst"] = doc.get("dst", {})
    return d
def _parse_filter_expression(filter_expr: str) -> Dict[str, Any]:
    """
    Parse expressions such as:
      msg contains "ICMP echo"
      priority>2 action=block
    into MongoDB-compatible query dictionaries.
    """
    import re

    token_pattern = re.compile(
        r'(?P<field>[A-Za-z0-9_.]+)\s*'
        r'(?P<op>!=|>=|<=|>|<|=|contains)\s*'
        r'(?P<value>"[^"]+"|\'[^\']+\'|\S+)',
        re.IGNORECASE,
    )

    conditions = []
    for match in token_pattern.finditer(filter_expr):
        field = match.group("field")
        op = match.group("op").lower()
        raw_value = match.group("value").strip()

        if (raw_value.startswith('"') and raw_value.endswith('"')) or (
            raw_value.startswith("'") and raw_value.endswith("'")
        ):
            value = raw_value[1:-1]
        else:
            value = raw_value

        # Attempt numeric conversion when appropriate
        try:
            if "." in value:
                converted: Any = float(value)
            else:
                converted = int(value)
        except ValueError:
            converted = value

        if op == "contains":
            conditions.append({field: {"$regex": re.escape(value), "$options": "i"}})
        elif op == "=":
            conditions.append({field: converted})
        elif op == "!=":
            conditions.append({field: {"$ne": converted}})
        elif op == ">":
            conditions.append({field: {"$gt": converted}})
        elif op == "<":
            conditions.append({field: {"$lt": converted}})
        elif op == ">=":
            conditions.append({field: {"$gte": converted}})
        elif op == "<=":
            conditions.append({field: {"$lte": converted}})

    if not conditions:
        return {}
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


@router.get("/recent", response_model=Dict[str, Any])
def get_recent_alerts(
    sensor_id: Optional[str] = None,
    q: Optional[str] = Query(None, description="Tìm kiếm theo msg hoặc rule_id (legacy)"),
    filters: Optional[str] = Query(None, description="Advanced filter expression (e.g., 'rule_id=123 priority>2')"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    since_minutes: Optional[int] = Query(None, ge=1, le=525600, description="Tìm trong X phút gần nhất (max 1 year)"),
    from_time: Optional[str] = Query(None, description="Custom range start (ISO timestamp)"),
    to_time: Optional[str] = Query(None, description="Custom range end (ISO timestamp)"),
    realtime: bool = Query(False, description="Real-time streaming mode"),
):
    """
    Lấy các alert từ MongoDB với nhiều tùy chọn lọc
    - sensor_id: filter theo sensor (nếu có)
    - q: tìm kiếm theo msg hoặc rule_id (legacy, simple search)
    - filters: advanced filter expression with operators (=, !=, >, <, contains)
    - page: page number
    - page_size: số lượng alert trả về mỗi trang (mặc định 50)
    - since_minutes: lấy alert từ X phút gần đây
    - from_time, to_time: custom time range (ISO format)
    - realtime: if True, returns most recent alerts regardless of time range
    """
    cond: Dict[str, Any] = {}
    
    # Sensor filter
    if sensor_id:
        cond["sensor_id"] = sensor_id
    
    # Advanced filter expression
    if filters:
        filter_cond = _parse_filter_expression(filters)
        if filter_cond:
            if "$and" in cond:
                cond["$and"].append(filter_cond)
            elif len(cond) > 0:
                cond = {"$and": [cond, filter_cond]}
            else:
                cond.update(filter_cond)
    
    # Legacy simple search (backward compatibility)
    elif q:
        cond["$or"] = [
            {"msg": {"$regex": q, "$options": "i"}},
            {"rule_id": {"$regex": q, "$options": "i"}}
        ]
    
    # Time range handling
    if realtime:
        # Real-time mode: get most recent alerts (last 5 minutes)
        since_ts = datetime.utcnow() - timedelta(minutes=5)
        cond["ingested_at"] = {"$gte": since_ts.isoformat()}
    elif from_time and to_time:
        # Custom time range - use ingested_at which is standard ISO
        cond["ingested_at"] = {"$gte": from_time, "$lte": to_time}
    elif from_time:
        # Only from_time specified
        cond["ingested_at"] = {"$gte": from_time}
    elif to_time:
        # Only to_time specified
        cond["ingested_at"] = {"$lte": to_time}
    elif since_minutes:
        # Preset time range
        since_ts = datetime.utcnow() - timedelta(minutes=since_minutes)
        cond["ingested_at"] = {"$gte": since_ts.isoformat()}
    else:
        # Default: last 60 minutes
        since_ts = datetime.utcnow() - timedelta(minutes=60)
        cond["ingested_at"] = {"$gte": since_ts.isoformat()}

    total = db_sec.ids_alerts.count_documents(cond)
    skip = (page - 1) * page_size
    alerts = list(db_sec.ids_alerts.find(cond).sort([("ts", -1)]).skip(skip).limit(page_size))
    
    return {
        "items": [_to_dict(alert) for alert in alerts],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }
