import sys
sys.path.insert(0, '/home/console/app')

from app.database.mongo import db_sec
from datetime import datetime

# Get a sample alert to see timestamp format
alert = db_sec.ids_alerts.find_one()
if alert:
    print(f"Sample alert ts: {alert.get('ts')}")
    print(f"Type: {type(alert.get('ts'))}")
    
# Count total alerts
total = db_sec.ids_alerts.count_documents({})
print(f"\nTotal alerts in DB: {total}")

# Try to find alerts with timestamp comparison
from_time = "2025-10-01T00:00:00"
to_time = "2025-10-31T23:59:59"

count_with_filter = db_sec.ids_alerts.count_documents({
    "ts": {"$gte": from_time, "$lte": to_time}
})
print(f"Alerts in October 2025 (string comparison): {count_with_filter}")

# Get one alert from October to see its exact timestamp
oct_alert = db_sec.ids_alerts.find_one({"ts": {"$regex": "^2025-10"}})
if oct_alert:
    print(f"\nSample October alert ts: {oct_alert.get('ts')}")
