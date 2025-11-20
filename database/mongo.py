from pymongo import MongoClient, ASCENDING, TEXT
import os, dotenv

# MongoDB connection with authentication
dotenv.load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
_client = MongoClient(MONGO_URI)
# Expose DB handles (dùng chung toàn app)
db_ioc = _client["misp_ioc"] 
db_sec = _client["sec_events"]

def ping() -> bool:
    _client.admin.command("ping")
    return True