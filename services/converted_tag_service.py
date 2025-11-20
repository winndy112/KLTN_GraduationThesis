from typing import Dict, Any, List
from app.database.collections import col_iocs, col_rule_items
from app.models.converted_tag_models import ConvertedTagRequest, ConvertedTagScope

def _attr_ids_from_sids(sids: List[int]) -> List[int]:
    cursor = col_rule_items.find(
        {"sid": {"$in": sids}},
        {"metadata.attr_id": 1}
    )
    attr_ids: List[int] = []
    for doc in cursor:
        meta = doc.get("metadata") or {}
        aid = meta.get("attr_id")
        if aid is not None:
            attr_ids.append(aid)
    # unique
    return list(set(attr_ids))

def toggle_converted_tag(req: ConvertedTagRequest) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    tag = req.tag

    # --- build filter ---
    if req.scope == ConvertedTagScope.event:
        q["event_id"] = req.event_id
    elif req.scope == ConvertedTagScope.sid:
        attr_ids = _attr_ids_from_sids(req.sids or [])
        if not attr_ids:
            return {
                "ok": True,
                "action": req.action,
                "scope": req.scope,
                "matched": 0,
                "modified": 0,
                "reason": "no attr_id found for given sids",
            }
        q["attr_id"] = {"$in": attr_ids}
    else:
        # scope = all -> để trống, áp vào toàn bộ collection
        pass

    # --- build update ---
    if req.action == "tag":
        update = {"$addToSet": {"tags": tag}}
        # không cần điều kiện tags hiện có
    else:  # untag
        # chỉ untag những doc đang có tag
        q["tags"] = tag
        update = {
            "$pull": {"tags": tag},
            "$unset": {
                "converted_at": "",
                "converted_rule_set_id": "",
                "converted_rule_set_version": "",
            },
        }       

    res = col_iocs.update_many(q, update)

    return {
        "ok": True,
        "action": req.action,
        "scope": req.scope,
        "tag": tag,
        "matched": res.matched_count,
        "modified": res.modified_count,
    }