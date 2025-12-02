import os

# Configuration for the Sensor Agent
# This runs on the Sensor Machine

# Zeek Log Directory (Default: /usr/local/zeek/logs)
ZEEK_LOG_DIR = os.getenv("ZEEK_LOG_DIR", "/opt/zeek/logs")
CURRENT_LOG_DIR = os.path.join(ZEEK_LOG_DIR, "current")
OLD_LOG_DIR = os.path.join(ZEEK_LOG_DIR, "*.tgz")

# API Configuration
HOST = os.getenv("SENSOR_HOST", "0.0.0.0")
PORT = int(os.getenv("SENSOR_PORT", 8001))
