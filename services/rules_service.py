from typing import List, Dict, Any, Tuple
from bson import ObjectId
from datetime import datetime
import os

from app.database.collections import (
    col_iocs, col_events, col_rule_items, col_rule_sets,
    col_rule_set_items, next_sid
)
from app.models.rule_models import RuleItem, RuleSet, RuleSetItem
from app.services.rule_converter import ioc_to_rule

CONVERTED_TAG = os.getenv("CONVERTED_TAG") or "console:converted"


# Version: YYYY.MM.DD-HHMMSS-e<event_id>[-NN] (duy nhất)
def _new_unique_version(event_id: int) -> str:
    base = datetime.utcnow().strftime("%Y.%m.%d-%H%M%S") + f"-e{int(event_id)}"
    v = base
    n = 0
    while col_rule_sets.find_one({"version": v}, {"_id": 1}):
        n += 1
        v = f"{base}-{n:02d}"
    return v


def upsert_rule_item(rule_doc: Dict[str, Any]) -> str:
    """
    Lưu hoặc lấy rule đã có theo rule_hash. Trả về _id (string).
    Yêu cầu rule_doc chứa 'sid' (đã cấp từ next_sid()) và các field hợp RuleItem.
    """
    found = col_rule_items.find_one({"rule_hash": rule_doc["rule_hash"]}, {"_id": 1})
    if found:
        return str(found["_id"])

    item_doc = RuleItem(
        sid=rule_doc.pop("sid"),
        msg=rule_doc["msg"],
        rule_text=rule_doc["rule_text"],
        rule_hash=rule_doc["rule_hash"],
        protocol=rule_doc["protocol"],
        src_sel=rule_doc["src_sel"],
        dst_sel=rule_doc["dst_sel"],
        buffers=rule_doc.get("buffers", []),
        keywords=rule_doc.get("keywords", []),
        flow=rule_doc.get("flow", {}),
        flowbits=rule_doc.get("flowbits", {}),
        references=rule_doc.get("references", []),
        metadata=rule_doc.get("metadata", {}),
        mitre=rule_doc.get("mitre", []),
        classtype=rule_doc.get("classtype", "trojan-activity"),
        priority=rule_doc.get("priority", 1),
        gid=1,
        current_rev=1,
    ).model_dump()

    res = col_rule_items.insert_one(item_doc)
    return str(res.inserted_id)


def build_rules_for_event(event_id: int, only_new: bool = True) -> Dict[str, Any]:
    event = col_events.find_one({"event_id": int(event_id)}) or {}
    event_uuid = event.get("uuid", "")

    # Lọc IOC: to_ids=true HOẶC (type="snort" và value chứa "alert")
    ioc_filter: Dict[str, Any] = {
        "event_id": int(event_id),
        "$or": [
            {"to_ids": True},
            {"type": "snort", "value": {"$regex": "alert", "$options": "i"}}
        ]
    }
    
    if only_new:
        ioc_filter["tags"] = {"$ne": CONVERTED_TAG}

    cur = col_iocs.find(
        ioc_filter,
        {"_id": 1, "type": 1, "value": 1, "event_uuid": 1, "event_id": 1, "attr_id": 1, "source": 1}
    )

    made_links: List[Tuple[str, int]] = []   # (rule_item_id, sid)
    touched_ioc_ids: List[ObjectId] = []

    for ioc in cur:
        sid = next_sid()
        rule_payload = ioc_to_rule(ioc, sid)  # trả về rule_text, rule_hash, msg, ...
        rule_id = upsert_rule_item({**rule_payload, "sid": sid})
        made_links.append((rule_id, sid))
        touched_ioc_ids.append(ioc["_id"])

    if not made_links:
        return {"set_id": None, "count": 0, "version": None, "event_id": int(event_id), "status": "noop"}

    # Tạo RuleSet
    version = _new_unique_version(event_id)
    rs = RuleSet(
        name=f"misp-event-{event_id}",
        version=version,
        event_id=int(event_id),
        event_uuid=str(event_uuid),
        item_count=len(made_links),
        status="ready",
    ).model_dump()
    set_id = str(col_rule_sets.insert_one(rs).inserted_id)

    # Link items vào set — thêm set_version/gid/sid để hợp index & truy vấn theo version
    bulk = []
    for rid, sid in made_links:
        link_doc = RuleSetItem(set_id=set_id, item_id=rid, rev=1).model_dump()
        link_doc.update({"set_version": version, "gid": 1, "sid": sid})
        bulk.append(link_doc)
    col_rule_set_items.insert_many(bulk)

    # Cập nhật IOC đã convert
    now = datetime.utcnow()
    if touched_ioc_ids:
        col_iocs.update_many(
            {"_id": {"$in": touched_ioc_ids}},
            {
                "$addToSet": {"tags": CONVERTED_TAG},
                "$set": {
                    "converted_at": now,
                    "converted_rule_set_id": set_id,
                    "converted_rule_set_version": version,
                }
            }
        )

    # Cập nhật event
    col_events.update_one(
        {"event_id": int(event_id)},
        {
            "$addToSet": {"tags": CONVERTED_TAG},
            "$set": {
                "last_converted_at": now,
                "last_rule_set_id": set_id,
                "last_rule_set_version": version,
                "last_convert_count": len(made_links),
            }
        },
        upsert=False
    )

    return {"set_id": set_id, "count": len(made_links), "version": version, "event_id": int(event_id), "status": "ok"}


def build_rules_for_all_new() -> List[Dict[str, Any]]:
    """Mỗi event tạo 1 set; chỉ convert IOC (to_ids=true HOẶC type=snort với value chứa alert) CHƯA có tag console:converted."""
    results: List[Dict[str, Any]] = []
    event_ids = col_iocs.distinct(
        "event_id",
        {
            "$or": [
                {"to_ids": True},
                {"type": "snort", "value": {"$regex": "alert", "$options": "i"}}
            ],
            "tags": {"$ne": CONVERTED_TAG}
        }
    )
    for eid in event_ids:
        results.append(build_rules_for_event(int(eid), only_new=True))
    return results
