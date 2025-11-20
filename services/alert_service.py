from app.database.mongo import db_sec
from app.models.alert_models import Alert

async def create_alert(alert: Alert):
    db_sec.ids_alerts.insert_one(alert.dict())  # Insert alert vào MongoDB
