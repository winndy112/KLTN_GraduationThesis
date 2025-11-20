from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pymongo.errors import PyMongoError
from app.database.mongo import db_ioc
from app.api.helpers import _check_key
from app.models.sensor_models import Heartbeat, StatusUpdate
import asyncio

router = APIRouter(prefix="/api/v1/sensors", tags=["sensors"])
col = db_ioc["sensor_infor"]

# ===== Thresholds =====
STATUS_INTERVAL = 60       # 1 phút -> dormant
INACTIVE_INTERVAL = 180    # 3 phút -> inactive

# ===== Time helpers =====
def _now(): return datetime.now(timezone.utc)
def _iso(dt: datetime) -> str: return dt.isoformat()

def _compute_status_from_last_status(last_status_at: Optional[str]) -> str:
    """Tính toán trạng thái dựa trên mốc last_status_at."""
    if not last_status_at:
        return "inactive"
    try:
        dt = datetime.fromisoformat(last_status_at.replace("Z", "+00:00"))
    except Exception:
        return "inactive"
    diff = (_now() - dt).total_seconds()
    if diff <= STATUS_INTERVAL:
        return "active"
    if diff <= INACTIVE_INTERVAL:
        return "dormant"
    return "inactive"

# ===== In-memory scheduler =====
sensor_timers: Dict[str, Dict[str, asyncio.Task]] = {}

async def _delayed_flip(sensor_id: str, delay: int, target_status: str):
    """Sau delay giây, kiểm tra last_status_at; nếu quá ngưỡng -> đổi trạng thái."""
    try:
        await asyncio.sleep(delay)
        doc = col.find_one({"sensor_id": sensor_id}, {"last_status_at": 1, "status": 1})
        if not doc:
            return
        new_status = _compute_status_from_last_status(doc.get("last_status_at"))
        if new_status != target_status:
            return  # có status mới hơn, không đổi

        now = _now()
        update = {"status": target_status}
        if target_status == "dormant":
            update.setdefault("dormant_since", _iso(now))
        if target_status == "inactive":
            update.setdefault("inactive_since", _iso(now))
        col.update_one({"sensor_id": sensor_id}, {"$set": update})
    except asyncio.CancelledError:
        pass

def schedule_for(sensor_id: str):
    """Hủy timer cũ và đặt lại timer dormant/inactive mới."""
    timers = sensor_timers.get(sensor_id)
    if timers:
        for t in timers.values():
            if not t.done():
                t.cancel()

    loop = asyncio.get_event_loop()
    sensor_timers[sensor_id] = {
        "dormant": loop.create_task(_delayed_flip(sensor_id, STATUS_INTERVAL, "dormant")),
        "inactive": loop.create_task(_delayed_flip(sensor_id, INACTIVE_INTERVAL, "inactive")),
    }

# ===== Routes =====
@router.put("/heartbeat")
async def heartbeat(hb: Heartbeat, x_api_key: str = Header(None)):
    _check_key(hb.sensor_id, x_api_key)
    now = _now()
    d = hb.dict()

    try:
        col.update_one(
            {"sensor_id": hb.sensor_id},
            {
                "$set": {
                    "sensor_id": hb.sensor_id,
                    "hostname": d["hostname"],
                    "roles": d.get("roles", []),
                    "location": d.get("location"),
                    "ip_mgmt": d.get("ip_mgmt"),
                    "ifaces": d.get("ifaces", []),
                    "engine_versions": d.get("engine_versions", {}),
                    "auth": d.get("auth", {}),
                    "rule_version": d.get("rule_version"),
                    "cpu_pct": d["cpu_pct"],
                    "mem_pct": d["mem_pct"],
                    "disk_free_gb": d["disk_free_gb"],
                    "traffic": d.get("traffic", {}),
                    "alerts_window": d.get("alerts_window"),
                    "last_rule_update": d.get("last_rule_update"),
                    "last_heartbeat": _iso(now),
                    "status_interval_s": d.get("status_interval_s", STATUS_INTERVAL),
                    
                },
                "$setOnInsert": {
                    "enrolled_at": d.get("enrolled_at") or _iso(now),
                    "disabled": False,
                    "suppress_alerts": False,
                    "maintenance_until": None,
                    "status": "inactive",
                    "status_reason": "never_seen",
                },
            },
            upsert=True,
        )
        # không schedule status ở đây
        return {"ok": True, "at": _iso(now)}
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

@router.put("/status")
async def status_update(st: StatusUpdate, x_api_key: str = Header(None)):
    _check_key(st.sensor_id, x_api_key)
    now = _now()
    new_status = st.status.lower()
    reason = "ok" if new_status == "active" else "manual_inactive"

    # --- lấy desired_rule_versions hiện có từ DB ---
    doc = col.find_one(
        {"sensor_id": st.sensor_id},
        {"desired_rule_versions": 1, "rule_versions": 1}
    ) or {}
    desired_versions: List[str] = doc.get("desired_rule_versions", []) or []

    # --- xác định các version sensor đang chạy ---
    installed_versions: List[str] = st.rule_versions or []
    if not installed_versions and st.rule_version:
        installed_versions = [st.rule_version]
    if not installed_versions:
        # fallback từ DB nếu status không gửi rule_versions
        installed_versions = doc.get("rule_versions", []) or []

    installed_set = set(installed_versions)
    desired_set = set(desired_versions)
    missing_versions = sorted(list(desired_set - installed_set))

    try:
        update: Dict[str, Any] = {
            "last_status_at": _iso(now),
            "status_reason": reason,
            "rule_version": st.rule_version,
            "rule_versions": installed_versions,
        }

        if new_status == "active":
            update.update({"status": "active", "dormant_since": None})
        elif new_status == "dormant":
            update.update({"status": "dormant", "dormant_since": _iso(now)})
        else:  # inactive
            update.update({"status": "inactive", "inactive_since": _iso(now)})

        col.update_one({"sensor_id": st.sensor_id}, {"$set": update}, upsert=True)
        schedule_for(st.sensor_id)

        return {
            "ok": True,
            "status": update["status"],
            "at": _iso(now),

            # block rule-sync cho sensor
            "installed_rule_versions": installed_versions,
            "desired_rule_versions": desired_versions,
            "missing_rule_versions": missing_versions,
        }
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

@router.get("/{sensor_id}/check_now")
async def check_now(sensor_id: str):
    """Nút 'Check status right now' – tính và cập nhật trạng thái tức thời."""
    now = _now()
    doc = col.find_one(
        {"sensor_id": sensor_id},
        {"last_status_at": 1, "status": 1, "dormant_since": 1, "inactive_since": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Sensor not found")

    new_status = _compute_status_from_last_status(doc.get("last_status_at"))
    update = {"status": new_status}
    if new_status == "dormant" and not doc.get("dormant_since"):
        update["dormant_since"] = _iso(now)
    if new_status == "inactive" and not doc.get("inactive_since"):
        update["inactive_since"] = _iso(now)
    if new_status == "active":
        update["dormant_since"] = None
        update["inactive_since"] = None

    col.update_one({"sensor_id": sensor_id}, {"$set": update})
    schedule_for(sensor_id)

    return {
        "ok": True,
        "sensor_id": sensor_id,
        "status": new_status,
        "last_status_at": doc.get("last_status_at"),
        "checked_at": _iso(now),
    }
