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



# def _to_dict(doc: Dict[str, Any]) -> Dict[str, Any]:
#     d = dict(doc)
#     d["_id"] = str(d["_id"])
#     # gọn dữ liệu trả về
#     d["src"] = doc.get("src", {})
#     d["dst"] = doc.get("dst", {})
#     return d
# @router.get("/recent", response_model=List[Dict[str, Any]])
# def get_recent_alerts(
#     sensor_id: Optional[str] = None,
#     q: Optional[str] = Query(None, description="Tìm kiếm theo msg hoặc rule_id"),
#     limit: int = Query(50, ge=1, le=200),
#     since_minutes: int = Query(60, ge=1, le=1440),  # Tìm trong 60 phút gần nhất mặc định
# ):
#     """
#     Lấy các alert gần đây từ MongoDB
#     - sensor_id: filter theo sensor (nếu có)
#     - q: tìm kiếm theo msg hoặc rule_id
#     - limit: số lượng alert trả về (mặc định 50)
#     - since_minutes: lấy alert từ X phút gần đây (mặc định 60)
#     """
#     cond: Dict[str, Any] = {}
#     if sensor_id:
#         cond["sensor_id"] = sensor_id
#     if q:
#         cond["$or"] = [{"msg": {"$regex": q, "$options": "i"}},
#                        {"rule_id": {"$regex": q, "$options": "i"}}]
#     since_ts = datetime.utcnow() - timedelta(minutes=since_minutes)
#     cond["ts"] = {"$gte": since_ts.isoformat()}

#     alerts = list(db_sec.ids_alerts.find(cond).sort([("ts", -1)]).limit(limit))
#     return [_to_dict(alert) for alert in alerts]