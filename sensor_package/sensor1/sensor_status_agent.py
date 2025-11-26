#!/usr/bin/env python3
"""
Sensor status agent for sensor-1.

- Sends a heartbeat payload at boot to upsert sensor metadata and rule versions.
- Sends /status active every STATUS_INTERVAL_S seconds to keep timers reset.
- Sends /status inactive when the process is terminated or the service stops.
- Downloads and applies missing rule versions advertised by the console.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict

import requests

API_BASE = os.getenv("API_BASE", "http://172.16.159.131:8000/api/v1")
SENSOR_URL = f"{API_BASE}/sensors"
RULES_URL = f"{API_BASE}/rules"
API_KEY = os.getenv("API_KEY", "K1-very-secret")
SENSOR_ID = os.getenv("SENSOR_ID", "sensor-1")
HOSTNAME = os.getenv("SENSOR_HOSTNAME", "sensor1")
ROLES = json.loads(os.getenv("SENSOR_ROLES", '["snort","zeek"]'))
LOCATION = os.getenv("SENSOR_LOCATION", "HCM")
OWNER_TEAM = os.getenv("SENSOR_OWNER_TEAM", "SOC")
RULE_ENGINE = os.getenv("RULE_ENGINE", "snort3")
RULE_VER = os.getenv("RULE_VERSION", "2025.10.24-01")
STATUS_INTERVAL_S = int(os.getenv("STATUS_INTERVAL", "10"))
TIMEOUT_S = int(os.getenv("SENSOR_TIMEOUT", "5"))
LOG_FILE = os.getenv("STATUS_AGENT_LOG", "/home/sensor1/sensor_status_agent.log")
RULE_DIR = Path(os.getenv("RULE_DIR", "/usr/local/etc/rules"))
RULE_VERSIONS_FILE = RULE_DIR / "VERSIONS.json"
MGMT_IFACE = os.getenv("MGMT_IFACE", "ens37")

Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("sensor-status")

INSTALLED_VERSIONS: List[str] = []
IP_MGMT: Optional[str] = None
IFACES: List[str] = []


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_network() -> None:
    """Populate IFACES and IP_MGMT information using psutil if available."""
    global IP_MGMT, IFACES
    try:
        import psutil
        import socket
        import ipaddress
    except Exception as exc:
        log.warning("psutil not available, keep defaults: %s", exc)
        IFACES = ["unknown"]
        IP_MGMT = "0.0.0.0"
        return

    try:
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
    except Exception as exc:
        log.warning("Failed to read interfaces via psutil: %s", exc)
        IFACES = ["unknown"]
        IP_MGMT = "0.0.0.0"
        return

    IFACES = [
        name for name, st in stats.items()
        if name != "lo" and st.isup
    ] or ["unknown"]

    def find_first_private(iface_list: List[str]) -> Optional[str]:
        for name in iface_list:
            for addr in addrs.get(name, []):
                if addr.family == socket.AF_INET:
                    ip = addr.address
                    try:
                        ip_obj = ipaddress.ip_address(ip)
                        if ip_obj.is_private and not ip.startswith("169.254."):
                            return ip
                    except ValueError:
                        continue
        return None

    mgmt_ip = None
    if MGMT_IFACE and MGMT_IFACE in addrs and MGMT_IFACE in stats and stats[MGMT_IFACE].isup:
        mgmt_ip = find_first_private([MGMT_IFACE])
    if not mgmt_ip:
        mgmt_ip = find_first_private(IFACES)

    IP_MGMT = mgmt_ip or "0.0.0.0"
    log.info("Detected IFACES=%s MGMT_IFACE=%s IP_MGMT=%s", IFACES, MGMT_IFACE, IP_MGMT)


def load_installed_versions() -> List[str]:
    global INSTALLED_VERSIONS, RULE_VER
    if RULE_VERSIONS_FILE.is_file():
        try:
            INSTALLED_VERSIONS = json.loads(RULE_VERSIONS_FILE.read_text())
        except Exception:
            INSTALLED_VERSIONS = []
    if not INSTALLED_VERSIONS:
        INSTALLED_VERSIONS = [RULE_VER]
    INSTALLED_VERSIONS = sorted(set(INSTALLED_VERSIONS))
    RULE_VER = INSTALLED_VERSIONS[-1]
    return INSTALLED_VERSIONS


def save_installed_versions() -> None:
    RULE_DIR.mkdir(parents=True, exist_ok=True)
    RULE_VERSIONS_FILE.write_text(json.dumps(INSTALLED_VERSIONS))


def get_cpu_mem() -> Dict[str, float]:
    try:
        import psutil
        return {
            "cpu_pct": round(psutil.cpu_percent(interval=0.2), 2),
            "mem_pct": round(psutil.virtual_memory().percent, 2),
        }
    except Exception:
        return {"cpu_pct": 0.0, "mem_pct": 0.0}


def get_disk_free_gb(path: str = "/") -> float:
    total, used, free = shutil.disk_usage(path)
    return round(free / (1024 ** 3), 2)


def get_engine_versions() -> Dict[str, str]:
    version_str = RULE_ENGINE
    try:
        out = subprocess.run(
            ["snort", "-V"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        for line in out.stdout.splitlines():
            if "Version" in line:
                version_str = line.strip()
                break
    except Exception:
        pass
    return {"rule_engine": RULE_ENGINE, "rule_engine_raw": version_str}


def download_rule_tgz(version: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading rules %s", version)
    response = requests.get(
        f"{RULES_URL}/{version}/file",
        headers={"X-API-Key": API_KEY},
        timeout=TIMEOUT_S,
        stream=True,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Rule download failed: {response.status_code} {response.text}")
    with open(dest, "wb") as file_handle:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file_handle.write(chunk)


def apply_rules_from_tgz(version: str, tgz: Path) -> None:
    tmp = RULE_DIR / ".tmp_rules"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with tarfile.open(tgz, "r:gz") as tar:
        tar.extractall(tmp)

    src = tmp / "console.rules"
    dst = RULE_DIR / f"console_{version}.rules"
    shutil.move(src, dst)
    shutil.rmtree(tmp)
    try:
        subprocess.run(["systemctl", "reload", "snort3"], check=True)
    except Exception as exc:
        log.error("Snort reload error: %s", exc)


def sync_missing(versions: List[str]) -> None:
    global INSTALLED_VERSIONS, RULE_VER
    for version in versions:
        tgz = RULE_DIR / f"{version}.tgz"
        try:
            download_rule_tgz(version, tgz)
            apply_rules_from_tgz(version, tgz)
            tgz.unlink(missing_ok=True)
            INSTALLED_VERSIONS.append(version)
            INSTALLED_VERSIONS = sorted(set(INSTALLED_VERSIONS))
            RULE_VER = INSTALLED_VERSIONS[-1]
            save_installed_versions()
        except Exception as exc:
            log.error("Failed to install version %s: %s", version, exc)


def base_headers() -> Dict[str, str]:
    return {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def build_heartbeat() -> Dict[str, object]:
    cpu = get_cpu_mem()
    latest = INSTALLED_VERSIONS[-1]
    now = utcnow_iso()
    return {
        "sensor_id": SENSOR_ID,
        "hostname": HOSTNAME,
        "roles": ROLES,
        "location": LOCATION,
        "ip_mgmt": IP_MGMT,
        "ifaces": IFACES,
        "engine_versions": get_engine_versions(),
        "auth": {"owner_team": OWNER_TEAM},
        "status": "active",
        "rule_version": latest,
        "rule_versions": INSTALLED_VERSIONS,
        "cpu_pct": cpu["cpu_pct"],
        "mem_pct": cpu["mem_pct"],
        "disk_free_gb": get_disk_free_gb(),
        "status_interval_s": STATUS_INTERVAL_S,
        "last_heartbeat": now,
        "enrolled_at": now,
    }


def send_heartbeat() -> None:
    try:
        requests.put(
            f"{SENSOR_URL}/heartbeat",
            json=build_heartbeat(),
            headers=base_headers(),
            timeout=TIMEOUT_S,
        )
        log.info("Heartbeat sent")
    except requests.RequestException as exc:
        log.error("Failed to send heartbeat: %s", exc)


def send_status(state: str) -> None:
    latest = INSTALLED_VERSIONS[-1]
    payload = {
        "sensor_id": SENSOR_ID,
        "status": state,
        "rule_version": latest,
        "rule_versions": INSTALLED_VERSIONS,
    }
    try:
        response = requests.put(
            f"{SENSOR_URL}/status",
            json=payload,
            headers=base_headers(),
            timeout=TIMEOUT_S,
        )
    except requests.RequestException as exc:
        log.error("Failed to send status %s: %s", state, exc)
        return

    if response.status_code != 200:
        log.warning("Console rejected status %s: %s %s", state, response.status_code, response.text)
        return

    log.info("Status %s sent", state)
    missing = response.json().get("missing_rule_versions", [])
    if missing:
        log.info("Syncing missing rules: %s", missing)
        sync_missing(missing)


def handle_exit(signum, frame):  # type: ignore[unused-argument]
    log.info("Received signal %s, marking sensor inactive", signum)
    try:
        send_status("inactive")
    finally:
        sys.exit(0)


signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)


def main() -> None:
    detect_network()
    load_installed_versions()
    save_installed_versions()
    send_heartbeat()

    last = 0.0
    while True:
        now = time.time()
        if now - last >= STATUS_INTERVAL_S:
            send_status("active")
            last = now
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - final guard for systemd
        log.exception("Fatal error in sensor_status_agent: %s", exc)
        send_status("inactive")
        raise
