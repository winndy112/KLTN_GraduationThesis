#!/usr/bin/env python3
"""
Agent that tails Snort JSON alerts and pushes them to the console in batches.
The defaults match the existing on-prem sensor-1 deployment but can be
overridden via environment variables to simplify reuse on additional sensors.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

import requests

DEFAULT_CONSOLE_URL = "http://172.16.159.131:8000/api/v1/alerts/push"
DEFAULT_SENSOR_ID = "sensor-1"
DEFAULT_SNORT_LOG = "/var/log/snort/alert_json.txt"
DEFAULT_AGENT_LOG = "/var/log/snort/push_agent.log"

CONSOLE_URL = os.getenv("CONSOLE_URL", DEFAULT_CONSOLE_URL)
API_KEY = os.getenv("API_KEY", "K1-very-secret")
SENSOR_ID = os.getenv("SENSOR_ID", DEFAULT_SENSOR_ID)
SNORT_LOG_FILE = os.getenv("SNORT_LOG_FILE", DEFAULT_SNORT_LOG)
AGENT_LOG_FILE = os.getenv("AGENT_LOG_FILE", DEFAULT_AGENT_LOG)
TIMEOUT = int(os.getenv("PUSH_TIMEOUT", "5"))
BATCH_SIZE = int(os.getenv("PUSH_BATCH_SIZE", "10"))
FLUSH_INTERVAL = float(os.getenv("PUSH_FLUSH_INTERVAL", "5"))

Path(AGENT_LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=AGENT_LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("push_agent")


def send_alerts(alerts_batch: List[Dict[str, Any]]) -> None:
    """Push a batch of alerts to the console."""
    if not alerts_batch:
        return

    headers = {"X-API-Key": API_KEY}
    try:
        response = requests.post(
            CONSOLE_URL,
            json=alerts_batch,
            headers=headers,
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            logger.info("Sent %s alerts successfully", len(alerts_batch))
        else:
            logger.warning(
                "Failed to send alerts (%s): %s",
                response.status_code,
                response.text,
            )
    except requests.exceptions.RequestException as exc:
        logger.error("Error sending alerts: %s", exc)


def read_snort_log() -> None:
    """Tail the Snort JSON log file and push alerts in batches."""
    alerts_batch: List[Dict[str, Any]] = []
    last_send_time = time.time()

    logger.info("Push Agent started, monitoring Snort log %s", SNORT_LOG_FILE)

    try:
        with open(SNORT_LOG_FILE, encoding="utf-8") as handle:
            handle.seek(0, os.SEEK_END)  # Skip existing contents
            while True:
                line = handle.readline()
                if line:
                    try:
                        alert = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("Skipping malformed JSON line")
                        continue

                    alert["sensor_id"] = SENSOR_ID
                    alert["ingested_at"] = datetime.now(timezone.utc).isoformat()
                    alerts_batch.append(alert)

                    if len(alerts_batch) >= BATCH_SIZE:
                        send_alerts(alerts_batch)
                        alerts_batch.clear()
                        last_send_time = time.time()
                else:
                    if alerts_batch and (time.time() - last_send_time) > FLUSH_INTERVAL:
                        send_alerts(alerts_batch)
                        alerts_batch.clear()
                        last_send_time = time.time()
                    time.sleep(0.2)
    except FileNotFoundError:
        logger.error("Snort log file not found: %s", SNORT_LOG_FILE)
    except Exception as exc:  # pragma: no cover - safety net for prod agent
        logger.exception("Unexpected error in push agent: %s", exc)


if __name__ == "__main__":
    read_snort_log()
