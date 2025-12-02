import argparse
import json
import time
import requests
import os
import subprocess
import logging
import threading
import ipaddress
from datetime import datetime, timezone
from typing import List, Dict, Any
from zeek_parser import parse_zeek_header, parse_zeek_line

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_rules(rules_file: str) -> List[Dict]:
    try:
        with open(rules_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load rules from {rules_file}: {e}")
        return []

def check_condition(record_value: Any, op: str, rule_value: Any) -> bool:
    try:
        if op == 'equals':
            return record_value == rule_value
        elif op == 'not_equals':
            return record_value != rule_value
        elif op == 'contains':
            return rule_value in str(record_value)
        elif op == 'startswith':
            return str(record_value).startswith(rule_value)
        elif op == 'endswith':
            return str(record_value).endswith(rule_value)
        elif op == 'endswith_any':
            return any(str(record_value).endswith(x) for x in rule_value)
        elif op == 'in':
            return record_value in rule_value
        elif op == 'not_in':
            return record_value not in rule_value
        elif op == 'gt':
            return float(record_value) > float(rule_value)
        elif op == 'lt':
            return float(record_value) < float(rule_value)
        elif op == 'in_cidr':
            # rule_value is list of CIDRs
            ip = ipaddress.ip_address(record_value)
            return any(ip in ipaddress.ip_network(cidr) for cidr in rule_value)
        elif op == 'not_in_cidr':
            ip = ipaddress.ip_address(record_value)
            return all(ip not in ipaddress.ip_network(cidr) for cidr in rule_value)
        else:
            logger.warning(f"Unknown operator: {op}")
            return False
    except Exception as e:
        # logger.debug(f"Condition check failed: {e}")
        return False

def match_rules(record: Dict[str, Any], rules: List[Dict]) -> List[Dict]:
    matches = []
    for rule in rules:
        if not rule.get('enabled', True):
            continue

        matched = True
        conditions = rule.get('conditions', [])
        
        # Support both old dict format and new list format
        if isinstance(conditions, dict):
            # Legacy format support
            for field, value in conditions.items():
                if field not in record:
                    matched = False
                    break
                if record[field] != value:
                    matched = False
                    break
        elif isinstance(conditions, list):
            # New format
            for cond in conditions:
                field = cond.get('field')
                op = cond.get('op', 'equals')
                value = cond.get('value')
                
                if field not in record:
                    matched = False
                    break
                
                if not check_condition(record.get(field), op, value):
                    matched = False
                    break
        
        if matched:
            matches.append(rule)
    return matches

def send_alert(alert: Dict, console_url: str, dry_run: bool):
    if dry_run:
        logger.info(f"[DRY RUN] Alert: {json.dumps(alert, default=str)}")
        return

    try:
        url = f"{console_url}/api/v1/alerts/processor"
        response = requests.post(url, json=alert, timeout=5)
        if response.status_code != 200:
            logger.error(f"Failed to send alert: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"Error sending alert: {e}")

def process_log_file(log_dir: str, log_type: str, sensor_id: str, rules: List[Dict], console_url: str, dry_run: bool):
    log_file = os.path.join(log_dir, f"{log_type}.log")
    logger.info(f"Starting monitor for {log_type} logs at {log_file}")
    
    # Filter rules for this log type
    type_rules = [r for r in rules if r.get('log_type') == log_type]
    if not type_rules:
        logger.info(f"No rules for log type {log_type}, skipping.")
        return

    # Use tail -F to handle rotation
    process = subprocess.Popen(
        ['tail', '-F', '-n', '0', log_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )

    header = {"fields": [], "types": []}
    
    # Read initial header if file exists
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            lines = []
            for _ in range(20): # Read first few lines for header
                line = f.readline()
                if line.startswith('#'):
                    lines.append(line)
                else:
                    break
            header = parse_zeek_header(lines)

    try:
        while True:
            line = process.stdout.readline()
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('#'):
                if line.startswith('#fields'):
                    header['fields'] = line.split()[1:]
                elif line.startswith('#types'):
                    header['types'] = line.split()[1:]
                continue

            record = parse_zeek_line(line, header['fields'], header['types'])
            if not record:
                continue

            matched_rules = match_rules(record, type_rules)
            for rule in matched_rules:
                ts = record.get('ts')
                if isinstance(ts, (int, float)):
                    timestamp = datetime.fromtimestamp(ts, tz=timezone.utc)
                else:
                    timestamp = datetime.now(timezone.utc)

                alert = {
                    "sensor_id": sensor_id,
                    "timestamp": timestamp.isoformat(),
                    "src_ip": record.get('id.orig_h'),
                    "src_port": record.get('id.orig_p'),
                    "dst_ip": record.get('id.resp_h'),
                    "dst_port": record.get('id.resp_p'),
                    "protocol": record.get('proto', 'unknown'),
                    "rule_id": rule.get('id'),
                    "rule_name": rule.get('name'),
                    "type": "zeek_processor",
                    "severity": rule.get('severity', 'medium'),
                    "category": rule.get('category', 'network'),
                    "log_type": log_type,
                    "message": f"Rule {rule.get('name')} matched",
                    "mitre_techniques": rule.get('mitre_techniques', []),
                    "tags": rule.get('tags', []),
                    "source": "zeek",
                    "uid": record.get('uid'),
                    "raw": record
                }
                
                send_alert(alert, console_url, dry_run)

    except Exception as e:
        logger.error(f"Error processing {log_type}: {e}")
    finally:
        process.terminate()

def main():
    parser = argparse.ArgumentParser(description="Zeek Log Processor")
    parser.add_argument("--sensor-id", required=True, help="Sensor ID")
    parser.add_argument("--log-dir", required=True, help="Directory containing Zeek logs")
    parser.add_argument("--rules", required=True, help="Path to rules JSON file")
    parser.add_argument("--console-url", required=True, help="Console API URL")
    parser.add_argument("--dry-run", action="store_true", help="Print alerts instead of sending")
    
    args = parser.parse_args()
    
    rules = load_rules(args.rules)
    logger.info(f"Loaded {len(rules)} rules")
    
    # Identify unique log types from rules
    log_types = set(r.get('log_type') for r in rules if r.get('log_type'))
    if not log_types:
        logger.warning("No log_type specified in rules, defaulting to 'conn'")
        log_types = {'conn'}
    
    threads = []
    for log_type in log_types:
        t = threading.Thread(
            target=process_log_file,
            args=(args.log_dir, log_type, args.sensor_id, rules, args.console_url, args.dry_run),
            daemon=True
        )
        t.start()
        threads.append(t)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")

if __name__ == "__main__":
    main()
