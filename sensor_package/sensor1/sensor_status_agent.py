#!/usr/bin/env python3
import time, logging, requests, shutil, subprocess, signal, sys, json, tarfile,                                                                                                                                                                                                                                              socket, ipaddress
from datetime import datetime, timezone
from typing import Dict, Any, List
from pathlib import Path

# ===== CONFIG (SENSOR-1) =====
API_BASE    = "http://172.16.159.131:8000/api/v1"
SENSOR_URL  = f"{API_BASE}/sensors"
RULES_URL   = f"{API_BASE}/rules"

API_KEY     = "K1-very-secret"
SENSOR_ID   = "sensor-1"
HOSTNAME    = "sensor1"

ROLES       = ["snort", "zeek"]
LOCATION    = "HCM"
OWNER_TEAM  = "SOC"

RULE_ENGINE = "snort3"
RULE_VER    = "2025.10.24-01"

IP_MGMT     = None
IFACES      = []

STATUS_INTERVAL_S = 10
TIMEOUT_S = 5
LOG_FILE  = "/home/sensor1/sensor_status_agent.log"

RULE_DIR = Path("/usr/local/etc/rules")
RULE_VERSIONS_FILE = RULE_DIR / "VERSIONS.json"
MGMT_IFACE = "ens37"   # interface dùng làm IP quản trị
# ==== phần dưới giống SENSOR-1 hoàn toàn ====

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("sensor-status")

INSTALLED_VERSIONS: List[str] = []

def utcnow_iso(): return datetime.now(timezone.utc).isoformat()
def detect_network():
    """
    - IP_MGMT: Ưu tiên IP v4 private của MGMT_IFACE (nếu interface UP & có IP)
               Nếu không thì fallback: private IP đầu tiên trên interface UP.
    - IFACES : Tất cả interface UP (trừ lo)
    """
    global IP_MGMT, IFACES

    try:
        import psutil, socket, ipaddress
    except Exception as e:
        log.warning(f"psutil not available, keep defaults: {e}")
        return

    try:
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
    except Exception as e:
        log.warning(f"Failed to read interfaces via psutil: {e}")
        return

    # ---- Collect UP interfaces (except lo)
    ifaces = []
    for name, st in stats.items():
        if name == "lo":
            continue
        if not st.isup:
            continue
        ifaces.append(name)

    IFACES = ifaces or ["unknown"]

    # ---- 1) Try MGMT_IFACE first
    mgmt_ip = None
    if MGMT_IFACE and MGMT_IFACE in addrs and MGMT_IFACE in stats:
        if stats[MGMT_IFACE].isup:
            for addr in addrs[MGMT_IFACE]:
                if addr.family == socket.AF_INET:
                    ip = addr.address
                    try:
                        ip_obj = ipaddress.ip_address(ip)
                        if ip_obj.is_private and not ip.startswith("169.254."):
                            mgmt_ip = ip
                            break
                    except ValueError:
                        continue

    # ---- 2) Fallback: any first private IP
    if not mgmt_ip:
        for name in IFACES:
            for addr in addrs.get(name, []):
                if addr.family == socket.AF_INET:
                    ip = addr.address
                    try:
                        ip_obj = ipaddress.ip_address(ip)
                        if ip_obj.is_private and not ip.startswith("169.254."):
                            mgmt_ip = ip
                            break
                    except ValueError:
                        continue
            if mgmt_ip:
                break

    IP_MGMT = mgmt_ip or "0.0.0.0"
    log.info(f"Auto-detect MGMT_IFACE={MGMT_IFACE}, IP_MGMT={IP_MGMT}, IFACES={IFACES}")

def load_installed_versions():
    global INSTALLED_VERSIONS, RULE_VER
    if RULE_VERSIONS_FILE.is_file():
        try:
            INSTALLED_VERSIONS = json.loads(RULE_VERSIONS_FILE.read_text())
        except:
            INSTALLED_VERSIONS = []

    if not INSTALLED_VERSIONS:
        INSTALLED_VERSIONS = [RULE_VER]

    INSTALLED_VERSIONS = sorted(set(INSTALLED_VERSIONS))
    RULE_VER = INSTALLED_VERSIONS[-1]
    return INSTALLED_VERSIONS

def save_installed_versions():
    RULE_DIR.mkdir(parents=True, exist_ok=True)
    RULE_VERSIONS_FILE.write_text(json.dumps(INSTALLED_VERSIONS))

def get_cpu_mem():
    try:
        import psutil
        return {
            "cpu_pct": round(psutil.cpu_percent(interval=0.2),2),
            "mem_pct": round(psutil.virtual_memory().percent,2)
        }
    except:
        return {"cpu_pct":0, "mem_pct":0}

def get_disk_free_gb(path="/"):
    total, used, free = shutil.disk_usage(path)
    return round(free/(1024**3),2)

def get_engine_versions():
    ver = RULE_ENGINE
    try:
        out = subprocess.run(["snort","-V"],capture_output=True,text=True,timeout=2)
        for line in out.stdout.splitlines():
            if "Version" in line:
                ver = line.strip()
    except:
        pass
    return {"rule_engine": RULE_ENGINE, "rule_engine_raw": ver}

def download_rule_tgz(version, dest):
    url = f"{RULES_URL}/{version}/file"
    r = requests.get(url, headers={"X-API-Key":API_KEY}, timeout=TIMEOUT_S, stream=True)
    if r.status_code != 200:
        raise RuntimeError(r.text)
    with open(dest,"wb") as f:
        for c in r.iter_content(8192):
            if c: f.write(c)

def apply_rules_from_tgz(version, tgz):
    tmp = RULE_DIR / ".tmp_rules"
    if tmp.exists(): shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    with tarfile.open(tgz,"r:gz") as tar:
        tar.extractall(tmp)

    src = tmp / "console.rules"
    dst = RULE_DIR / f"console_{version}.rules"
    shutil.move(src, dst)
    shutil.rmtree(tmp)

    try:
        subprocess.run(["systemctl","reload","snort3"],check=True)
    except Exception as e:
        log.error(f"Snort reload error: {e}")

def sync_missing(versions):
    global INSTALLED_VERSIONS, RULE_VER
    for v in versions:
        tgz = RULE_DIR / f"{v}.tgz"
        try:
            download_rule_tgz(v, tgz)
            apply_rules_from_tgz(v, tgz)
            tgz.unlink(missing_ok=True)
            INSTALLED_VERSIONS.append(v)
            INSTALLED_VERSIONS = sorted(set(INSTALLED_VERSIONS))
            RULE_VER = INSTALLED_VERSIONS[-1]
            save_installed_versions()
        except Exception as e:
            log.error(f"Failed install version {v}: {e}")

def build_heartbeat():
    cpu = get_cpu_mem()
    latest = INSTALLED_VERSIONS[-1]
    return {
        "sensor_id": SENSOR_ID,
        "hostname": HOSTNAME,
        "roles": ROLES,
        "location": LOCATION,
        "ip_mgmt": IP_MGMT,
        "ifaces": IFACES,
        "engine_versions": get_engine_versions(),
        "auth": {"owner_team": OWNER_TEAM},

        "status":"active",
        "rule_version": latest,
        "rule_versions": INSTALLED_VERSIONS,

        "cpu_pct": cpu["cpu_pct"],
        "mem_pct": cpu["mem_pct"],
        "disk_free_gb": get_disk_free_gb(),
        "status_interval_s": STATUS_INTERVAL_S,
        "last_heartbeat": utcnow_iso(),
        "enrolled_at": utcnow_iso(),
    }

def send_heartbeat():
    requests.put(
        f"{SENSOR_URL}/heartbeat",
        json=build_heartbeat(),
        headers={"X-API-Key":API_KEY},
        timeout=TIMEOUT_S
    )
    log.info("Heartbeat sent")

def send_status(state):
    latest = INSTALLED_VERSIONS[-1]
    payload = {
        "sensor_id": SENSOR_ID,
        "status": state,
        "rule_version": latest,
        "rule_versions": INSTALLED_VERSIONS,
    }
    r = requests.put(
        f"{SENSOR_URL}/status",
        json=payload,
        headers={"X-API-Key":API_KEY},
        timeout=TIMEOUT_S
    )
    if r.status_code == 200:
        missing = r.json().get("missing_rule_versions", [])
        if missing:
            sync_missing(missing)

def _on_term(*a):
    send_status("inactive")
    sys.exit(0)

signal.signal(signal.SIGTERM,_on_term)
signal.signal(signal.SIGINT,_on_term)

def main():
    detect_network()
    load_installed_versions()
    send_heartbeat()

    last = 0
    while True:
        if time.time() - last >= STATUS_INTERVAL_S:
            send_status("active")
            last = time.time()
        time.sleep(1)

if __name__ == "__main__":
    main()
