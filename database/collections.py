from pymongo import ASCENDING, ReturnDocument
from .mongo import db_ioc
from  .mongo import db_sec

col_iocs           = db_ioc["iocs"]
col_events         = db_ioc["events"]
col_rule_items     = db_ioc["rule_items"]
col_rule_sets      = db_ioc["rule_sets"]
col_rule_set_items = db_ioc["rule_set_items"]
col_counters       = db_ioc["counters"]
col_sensor_infor   = db_ioc["sensor_infor"]
col_processor = db_sec["processor_alerts"]

def next_sid() -> int:
    # First, try to increment if document exists
    doc = col_counters.find_one_and_update(
        {"_id": "sid"},
        {"$inc": {"value": 1}},
        upsert=False,
        return_document=ReturnDocument.AFTER,
    )
    if doc:
        return int(doc["value"])
    
    # Document doesn't exist, create it with initial value and increment
    # Set initial value to 2_999_999, then increment to 3_000_000
    doc = col_counters.find_one_and_update(
        {"_id": "sid"},
        {"$setOnInsert": {"value": 2_999_999}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    # Now increment the newly created document
    doc = col_counters.find_one_and_update(
        {"_id": "sid"},
        {"$inc": {"value": 1}},
        return_document=ReturnDocument.AFTER,
    )
    return int(doc["value"])
def seed_sid_counter(default_start=3_000_000) -> int:
    # lấy sid lớn nhất hiện có (an toàn khi collection rỗng)
    max_doc = col_rule_items.find_one(
        {"sid": {"$type": "number"}},
        sort=[("sid", -1)],
        projection={"sid": 1, "_id": 0}
    )
    # counter lưu "giá trị cuối cùng đã cấp"
    last_value = (max_doc["sid"] if max_doc else default_start - 1)
    # nếu default_start lớn hơn, ưu tiên dải mới của bạn
    last_value = max(last_value, default_start - 1)

    col_counters.update_one(
        {"_id": "sid"},
        {"$set": {"value": int(last_value)}},
        upsert=True
    )
    return last_value

# tiện cho các module khác import *
__all__ = [
    "col_iocs","col_events","col_rule_items","col_rule_sets",
    "col_rule_set_items","col_counters","next_sid", "col_sensor_infor", "col_processor"
]