from fastapi import APIRouter, HTTPException, Header, Query
from app.models.alert_models import Alert
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Any, Dict
from bson import ObjectId
from app.database.mongo import db_sec, db_ioc
import os

# Parse API_KEYS from env: "sensor-1=key1,sensor-2=key2" -> {"sensor-1": "key1", "sensor-2": "key2"}
_api_keys_raw = os.getenv("API_KEYS", "")
API_KEYS: Dict[str, str] = {}
if _api_keys_raw:
    for item in _api_keys_raw.split(","):
        item = item.strip()
        if "=" in item:
            sensor_id, key = item.split("=", 1)
            API_KEYS[sensor_id.strip()] = key.strip()

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

# ---- auth helper for admin operations (pull/tag) ----
def _admin_auth(x_admin_key: Optional[str] = Header(None)):
    want = os.getenv("CONSOLE_ADMIN_KEY")
    if not want or x_admin_key != want:
        raise HTTPException(401, "invalid admin key")

# check api_key 
def _check_key(sensor_id: str | None, x_api_key: str | None):
    if not sensor_id or not x_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    expected_key = API_KEYS.get(sensor_id)
    if not expected_key or expected_key != x_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

        
# Parsing timestamp
def _parse_ts(ts: str | None) -> str | None:
    """
    Snort/Zeek thường có dạng 'MM/DD-HH:MM:SS.ffffff'.
    Nếu bạn muốn ISO 8601, convert nhanh (gắn năm hiện tại).
    """
    if not ts:
        return None
    try:
        # ví dụ: 10/24-06:41:36.678258 -> 2025-10-24T06:41:36.678258
        now_year = datetime.utcnow().year
        dt = datetime.strptime(f"{now_year}-{ts.replace('/', '-').replace('-', ' ', 1)}", "%Y-%m-%d %H:%M:%S.%f")
        return dt.isoformat()
    except Exception:
        return ts  # giữ nguyên nếu không parse được

def _normalize(a: Dict[str, Any]) -> Dict[str, Any]:
    a = dict(a)

    # map trường hay gặp từ log của bạn
    # timestamp -> ts (ISO nếu parse được)
    if "ts" not in a:
        a["ts"] = _parse_ts(a.pop("timestamp", None))

    # rule -> rule_id (ví dụ: "1:10000001:0")
    if "rule" in a and "rule_id" not in a:
        a["rule_id"] = a.pop("rule")

    # class -> classification
    if "class" in a and "classification" not in a:
        a["classification"] = a.pop("class")

    # src/dst ip/port đồng nhất
    if "src_addr" in a or "dst_addr" in a or "src_port" in a or "dst_port" in a:
        a["src"] = {
            "ip": a.pop("src_addr", None),
            "port": a.pop("src_port", None),
        }
        a["dst"] = {
            "ip": a.pop("dst_addr", None),
            "port": a.pop("dst_port", None),
        }

    # điền mặc định nhẹ
    a.setdefault("priority", 3)
    a.setdefault("action", "allow")
    a.setdefault("proto", a.get("proto") or "IP")
    a.setdefault("ingested_at", datetime.utcnow().isoformat())

    return a