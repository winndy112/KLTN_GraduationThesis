from datetime import datetime
from typing import Literal, List, Dict, Any

from app.database.collections import col_rule_sets, col_sensor_infor
import os

RULE_ENGINE = os.getenv("RULE_ENGINE", "snort3")
def get_sensor_rule_stats(sensor_id: str) -> dict:
    info = col_sensor_infor.find_one({"sensor_id": sensor_id}) or {}
    versions = info.get("rule_versions", [])

    if not versions:
        return {"sensor_id": sensor_id, "versions": [], "total_rules": 0}

    cur = col_rule_sets.find(
        {"version": {"$in": versions}},
        {"version": 1, "item_count": 1, "_id": 0},
    )
    per_set = list(cur)
    total = sum(d.get("item_count", 0) for d in per_set)

    return {
        "sensor_id": sensor_id,
        "versions": per_set,      # [{version, item_count}, ...]
        "total_rules": total,
    }

def deploy_rule_set_version(
    version: str,
    target: Literal["all", "list"] = "all",
    sensors: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Deploy 1 rule_set theo version:
    - Đánh dấu rule_set này active + deployed_at
    - Append version vào desired_rule_versions của sensor_infor
    """
    rs = col_rule_sets.find_one({"version": version})
    if not rs:
        raise ValueError("rule_set not found")

    files = (rs.get("files") or {}).get("tar") or {}
    if not files.get("path"):
        raise RuntimeError("rule_set has no built file, call /build first")

    col_rule_sets.update_one(
        {"_id": rs["_id"]},
        {"$set": {"active": True, "deployed_at": datetime.utcnow(), "status": "deployed"}},
    )

    version = rs["version"]

    # desired_rule_versions là MẢNG các version cần có trên sensor
    if target == "all":
        q = {}
    else:
        q = {"sensor_id": {"$in": sensors or []}}

    upd = {
        "$addToSet": {  # append, không overwrite
            "desired_rule_versions": version
        },
        "$set": {
            "desired_rule_updated_at": datetime.utcnow(),
        },
    }
    res = col_sensor_infor.update_many(q, upd)

    return {
        "rule_set_version": version,
        "matched_sensors": res.matched_count,
        "modified_sensors": res.modified_count,
    }
