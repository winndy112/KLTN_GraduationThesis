import requests
import json
import time

# Configuration
API_URL = "http://localhost:8000/api/v1/alerts/processor"
API_KEY = "K1-very-secret"  # Matching the key in alerts.py for sensor-1

# Sample Alert Data
alert_data = {
  "sensor_id": "sensor-1",
  "timestamp": "2025-11-26T10:10:10Z",
  "src_ip": "172.16.10.128",
  "src_port": 52341,
  "dst_ip": "8.8.8.8",
  "dst_port": 53,
  "protocol": "udp",

  "rule_id": "ZEEK_DNS_SUSPICIOUS_TLD",
  "rule_name": "Suspicious DNS TLD (.ru/.xyz)",

  "rule_type": "pattern",
  "severity": "high",
  "category": "dns",
  "log_type": "dns",

  "message": "DNS query to suspicious TLD .ru",
  "mitre_techniques": ["T1071.004"],
  "tags": ["zeek", "dns", "suspicious_tld"],

  "source": "sensor-1",
  "uid": "Cyc1Vd2rXn9eDf",
  "raw": {
    "query": "example.ru",
    "qtype_name": "A"
  }
}

def test_push_alert():
    print(f"Sending request to {API_URL}...")
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY
    }
    
    try:
        response = requests.post(API_URL, json=alert_data, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("SUCCESS: Alert pushed successfully.")
        else:
            print("FAILURE: Failed to push alert.")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_push_alert()
