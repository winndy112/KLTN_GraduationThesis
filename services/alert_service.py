from app.database.mongo import db_sec
from app.models.alert_models import Alert, ProcessorAlert

async def create_alert(alert: Alert):
    db_sec.ids_alerts.insert_one(alert.dict())  # Insert alert vào MongoDB

async def save_processor_alert(alert: ProcessorAlert):
    result = db_sec.processor_alerts.insert_one(alert.dict())
    return str(result.inserted_id)
