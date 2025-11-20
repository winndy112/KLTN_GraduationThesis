import hashlib, ipaddress, re, os
from typing import Dict, Any, Tuple
from datetime import datetime


# --- ENV networks (mặc định dùng tên biến Snort) ---
HOME_NET = os.getenv("HOME_NET", "$HOME_NET")
EXTERNAL_NET = os.getenv("EXTERNAL_NET", "$EXTERNAL_NET")

# --- helpers ---
def join_tokens(tokens):
    # mỗi token KHÔNG có ; ở cuối
    return '; '.join(t.strip().rstrip(';') for t in tokens) + ';'

def sha1_hex(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def is_ip(v: str) -> bool:
    try:
        ipaddress.ip_address(v)
        return True
    except Exception:
        return False

def safe_msg(v: str) -> str:
    return v.replace('"', "'")[:180]

def parse_ip_port(v: str) -> Tuple[str, str]:
    """
    Nhận '1.2.3.4|443', '1.2.3.4:443', '1.2.3.4' -> (ip, port)
    """
    s = v.strip()
    ip, port = s, "any"
    for sep in ("|", ":"):
        if sep in s:
            left, right = s.split(sep, 1)
            ip, port = left.strip(), right.strip() or "any"
            break
    return ip, port or "any"

def parse_domain_ip(v: str) -> Tuple[str, str]:
    """
    Nhận 'evil.com|1.2.3.4' hoặc '1.2.3.4|evil.com'
    Trả (domain, ip) nếu detect được.
    """
    s = v.strip()
    dom, ip = "", ""
    if "|" in s:
        left, right = s.split("|", 1)
        left, right = left.strip(), right.strip()
        if is_ip(left):
            ip, dom = left, right
        elif is_ip(right):
            dom, ip = left, right
        else:
            dom = left
    else:
        # fallback: coi cả chuỗi là domain
        dom = s
    return dom, ip

# --- builders per type ---

def build_rule_for_domain(val: str, sid: int) -> Tuple[str, Dict[str, Any]]:
    msg = "TLS SNI suspicious domain"
    tokens = [
        f'msg:"{msg}"',
        'tls_sni', f'content:"{val}"', 'fast_pattern',
        f"sid:{sid}", "rev:1",
    ]
    # SRC: HOME_NET:any  ->  DST: EXTERNAL_NET:443
    text = f'alert tcp {HOME_NET} any -> {EXTERNAL_NET} 443 ({join_tokens(tokens)})'
    meta = {
        "protocol": "tcp",
        "src_sel": f"{HOME_NET}:any",
        "dst_sel": f"{EXTERNAL_NET}:443",
        "buffers": [{"name": "tls_sni", "content": val}],
        "keywords": ["tls_sni", "content", "fast_pattern"],
    }
    return msg, {"text": text, **meta}

def build_rule_for_ip(ip: str, sid: int, port: str = "any", role: str = "dst") -> Tuple[str, Dict[str, Any]]:
    msg = "Suspicious IP connection"
    tokens = [f'msg:"{msg}"', "flow:to_server,established", f"sid:{sid}", "rev:1"]
    dport = port or "any"

    if role == "src":
        # SRC: ip:any  ->  DST: EXTERNAL_NET:port
        text = f'alert ip {ip} any -> {EXTERNAL_NET} {dport} ({join_tokens(tokens)})'
        src_sel, dst_sel = f"{ip}:any", f"{EXTERNAL_NET}:{dport}"
    else:
        # SRC: HOME_NET:any  ->  DST: ip:port
        text = f'alert ip {HOME_NET} any -> {ip} {dport} ({join_tokens(tokens)})'
        src_sel, dst_sel = f"{HOME_NET}:any", f"{ip}:{dport}"

    meta = {"protocol": "ip", "src_sel": src_sel, "dst_sel": dst_sel, "buffers": [], "keywords": ["flow"]}
    return msg, {"text": text, **meta}

def build_rule_for_url(url: str, sid: int) -> Tuple[str, Dict[str, Any]]:
    host, path = url, "/"
    m = re.match(r"^(?:https?://)?([^/]+)(/.*)?$", url)
    if m:
        host, path = m.group(1), (m.group(2) or "/")

    msg = "HTTP request suspicious URL"
    tokens = [
        f'msg:"{msg}"',
        'http_header', 'content:"Host"', 'http_header', f'content:"{host}"',
        'http_uri', f'content:"{path}"', 'fast_pattern',
        'flow:to_server,established',
        f"sid:{sid}", "rev:1",
    ]
    # SRC: HOME_NET:any  ->  DST: EXTERNAL_NET:80
    text = f'alert tcp {HOME_NET} any -> {EXTERNAL_NET} 80 ({join_tokens(tokens)})'
    meta = {
        "protocol": "tcp",
        "src_sel": f"{HOME_NET}:any",
        "dst_sel": f"{EXTERNAL_NET}:80",
        "buffers": [{"name":"http_header","content":host},{"name":"http_uri","content":path}],
        "keywords": ["http_header", "http_uri", "content", "flow", "fast_pattern"],
    }
    return msg, {"text": text, **meta}

def build_rule_for_dnsq(name: str, sid: int) -> Tuple[str, Dict[str, Any]]:
    msg = "DNS query suspicious name"
    tokens = [f'msg:"{msg}"', 'dns_query', f'content:"{name}"', 'nocase', f"sid:{sid}", "rev:1"]
    # SRC: HOME_NET:any  ->  DST: EXTERNAL_NET:53
    text = f'alert udp {HOME_NET} any -> {EXTERNAL_NET} 53 ({join_tokens(tokens)})'
    meta = {
        "protocol": "udp",
        "src_sel": f"{HOME_NET}:any",
        "dst_sel": f"{EXTERNAL_NET}:53",
        "buffers": [{"name": "dns_query", "content": name}],
        "keywords": ["dns_query", "content", "nocase"],
    }
    return msg, {"text": text, **meta}




def _normalize_options_block(opts: str) -> str:
    # chuẩn hoá: tách theo ';', bỏ rỗng và dấu ';' cuối, ghép lại thành "...; ...;"
    parts = [p.strip().rstrip(';') for p in opts.split(';') if p.strip()]
    return '; '.join(parts) + ';' if parts else ''


def build_rule_for_snort(rule_line: str, fallback_sid: int) -> Tuple[str, Dict[str, Any]]:
    """
    Nhận 1 dòng rule Snort bắt đầu bằng 'alert ... ( ... )'
    - Nếu có sid:<n>; trong options -> dùng n cho DB
    - Nếu chưa có sid -> chèn sid:fallback_sid; rev:1;
    Trả về (msg, meta) với rule_text = raw rule (đã normalize options)
    """
    m = re.match(
        r'^\s*alert\s+(\w+)\s+([^\s]+)\s+([^\s]+)\s*->\s*([^\s]+)\s+([^\s]+)\s*\((.*)\)\s*$',
        rule_line, re.IGNORECASE | re.DOTALL
    )
    if not m:
        raise ValueError("Invalid Snort rule format")

    proto, src, sport, dst, dport, opts = m.groups()
    opts_norm = _normalize_options_block(opts)

    # msg (nếu có)
    msg_match = re.search(r'msg\s*:\s*"([^"]*)"', opts_norm, re.IGNORECASE)
    msg = msg_match.group(1) if msg_match else "Imported Snort rule"

    # sid trong rule (nếu có)
    sid_match = re.search(r'\bsid\s*:\s*(\d+)\s*;', opts_norm, re.IGNORECASE)
    db_sid = int(sid_match.group(1)) if sid_match else int(fallback_sid)

    # Nếu chưa có sid thì chèn sid + rev vào cuối
    if not sid_match:
        opts_norm = _normalize_options_block(opts_norm + f' sid:{db_sid}; rev:1;')

    rule_text = f'alert {proto} {src} {sport} -> {dst} {dport} ({opts_norm})'

    meta = {
        "protocol": proto.lower(),
        "src_sel": f"{src}:{sport}",
        "dst_sel": f"{dst}:{dport}",
        "buffers": [],
        "keywords": [],  # có thể parse thêm nếu cần
        "db_sid": db_sid,  # trả về để caller dùng làm gid/sid DB
    }
    return msg, {"text": rule_text, **meta}

# --- main dispatch ---

SNORTABLE_TYPES = {
    "domain", "hostname",
    "domain|ip",
    "ip-dst", "ip-src",
    "ip-dst|port", "ip-src|port",
    "url", "uri",
    "snort",
}

def ioc_to_rule(ioc: Dict[str, Any], sid: int) -> Dict[str, Any]:
    
    t = ioc.get("type", "").lower()
    v = str(ioc.get("value", "")).strip()

    msg, built = None, None

    # 1) Domain / hostname -> TLS SNI rule
    if t in ("domain", "hostname"):
        msg, built = build_rule_for_domain(v, sid)

    # 2) domain|ip -> ưu tiên domain cho DNS query
    elif t == "domain|ip":
        dom, ip = parse_domain_ip(v)
        name = dom or ip or v
        msg, built = build_rule_for_dnsq(name, sid)

    # 3) IP dst/src không port
    elif t == "ip-dst" and is_ip(v):
        msg, built = build_rule_for_ip(v, sid, role="dst")
    elif t == "ip-src" and is_ip(v):
        msg, built = build_rule_for_ip(v, sid, role="src")

    # 4) IP dst/src có port: '1.2.3.4|443' / '1.2.3.4:443'
    elif t == "ip-dst|port":
        ip, port = parse_ip_port(v)
        if is_ip(ip):
            msg, built = build_rule_for_ip(ip, sid, port=port, role="dst")
    elif t == "ip-src|port":
        ip, port = parse_ip_port(v)
        if is_ip(ip):
            msg, built = build_rule_for_ip(ip, sid, port=port, role="src")

    # 5) URL / URI
    elif t in ("url", "uri"):
        msg, built = build_rule_for_url(v, sid)
    elif t == "snort" and v.lower().startswith("alert"):
        msg, built = build_rule_for_snort(v, sid)
        # Nếu rule có sid riêng -> ghi đè sid DB bằng sid của rule
        if "db_sid" in built:
            sid = built.pop("db_sid")
    # 6) fallback generic cho mấy type khác (chỉ dùng khi muốn rất aggressive)
    if not built:
        msg = f"Generic match for {t}"
        text = (
            f'alert ip any any -> any any (msg:"{safe_msg(v)}"; '
            f'content:"{v}"; sid:{sid}; rev:1;)'
        )
        built = {
            "text": text,
            "protocol": "ip",
            "src_sel": "any:any",
            "dst_sel": "any:any",
            "buffers": [],
            "keywords": ["content"],
        }

    rule_hash = sha1_hex(f"{t}|{v}|{built['text']}")

    return {
        "msg": msg,
        "protocol": built["protocol"],
        "src_sel": built["src_sel"],
        "dst_sel": built["dst_sel"],
        "rule_text": built["text"],  
        "rule_hash": rule_hash,
        "buffers": built["buffers"],
        "keywords": built["keywords"],
        "flow": {},
        "flowbits": {},
        "references": [
            {"type": "misp", "value": str(ioc.get("event_uuid", ""))}
        ],
        "metadata": {
            "event_id": ioc.get("event_id"),
            "attr_id": ioc.get("attr_id"),
            "ioc_type": t,
            "pulled_at": (ioc.get("source", {}) or {}).get("pulled_at"),
        },
        "mitre": [
            {
                "status_default": "enabled",
                "since_version": datetime.utcnow().strftime("%Y.%m.%d-%H"),
            }
        ],
    }
