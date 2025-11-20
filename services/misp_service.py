#!/usr/bin/env python3
from __future__ import annotations
import os, re, time, logging
from typing import Tuple, Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
import urllib3, warnings
from pymongo.database import Database
from pymongo import UpdateOne
from dateutil.parser import isoparse
from pymisp import PyMISP

log = logging.getLogger("misp.service")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning, module="pymisp")
log.setLevel(os.getenv("MISP_LOG_LEVEL", "INFO").upper())

# ---------- small helpers ----------
def _to_dt(x) -> datetime:
    if isinstance(x, (int, float)): return datetime.fromtimestamp(int(x), tz=timezone.utc)
    dt = isoparse(str(x));  return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def _since_to_dt(since: str, now: datetime) -> datetime:
    s = (since or "").strip().lower()
    if s.endswith("d"): return now - timedelta(days=int(s[:-1]))
    if s.endswith("h"): return now - timedelta(hours=int(s[:-1]))
    return _to_dt(since)

def _split_pipe(v: str) -> Tuple[Optional[str], Optional[str]]:
    if v and "|" in v: a,b=v.split("|",1); return a.strip(), b.strip()
    return None, None

_HASH = {"md5","sha1","sha256","sha512","imphash","authentihash","tlsh"}
_NET  = {"ip-src","ip-dst","ip-src|port","ip-dst|port","domain","hostname","url","uri","dns"}

def _normalize(t: str, value: str) -> Dict[str, Any]:
    fam= "file" if (t in _HASH or t.startswith("filename|sha")) else "network" if t in _NET else "email" if t.startswith("email-") else "other"
    host=ip=port=algo=None
    if fam=="file":
        algo = t if t in _HASH else (value.split("|",1)[-1].split(":")[0].lower() if "|" in value else None)
    elif fam=="network":
        if t in {"domain","hostname"}: host=(value or "").lower()
        elif t in {"url","uri"}:
            m = re.match(r"^[a-z]+://([^/]+)", value or "", re.I); host = m.group(1).lower() if m else None
        elif t in {"ip-src","ip-dst"}: ip = value
        elif t in {"ip-src|port","ip-dst|port"}:
            left,right=_split_pipe(value or ""); ip=left; port=int(right) if right and right.isdigit() else None
    return {"type_family": fam, "hash_algo": algo, "host": host, "ip": ip, "port": port}

def _galaxies(E: dict) -> List[dict]:
    out=[]
    for G in E.get("Galaxy", []) or []:
        for C in G.get("GalaxyCluster", []) or []:
            item = {
                "galaxy_type": G.get("type"),
                "galaxy_uuid": G.get("uuid"),
                "cluster_value": C.get("value"),
                "cluster_uuid": C.get("uuid"),
                "namespace": G.get("namespace","misp-galaxy"),
                "tag": C.get("tag_name") or C.get("value"),
                "meta": C.get("meta") or {}
            }
            out.append(item)
    return out

# ---------- service ----------
class MISPService:
    def __init__(self, db_ioc: Database):
        self.db = db_ioc
        self.url = (os.getenv("MISP_URL") or "http://127.0.0.1").rstrip("/")
        self.verify = (os.getenv("MISP_VERIFY_SSL", "false").lower() == "true")
        self.key = os.getenv("MISP_KEY")
        self.imported_tag = os.getenv("MISP_IMPORTED_TAG", "console:imported")
        self.col_events = self.db["events"]
        self.col_iocs = self.db["iocs"]
        self._misp = None
        self._ensure_indexes()

    def _client(self):
        if not self.key: raise RuntimeError("MISP_KEY is not set")
        if self._misp is None:
            log.info("misp.client:init url=%s verify=%s", self.url, self.verify)
            self._misp = PyMISP(self.url, self.key, ssl=self.verify, timeout=30)    
        return self._misp

    def _ensure_indexes(self):
        self.col_events.create_index("uuid", unique=True)
        self.col_events.create_index([("published",1),("timestamp",-1)])
        self.col_events.create_index([("tags",1)])
        self.col_iocs.create_index("uuid", unique=True)
        self.col_iocs.create_index([("type",1),("value",1)])
        self.col_iocs.create_index("event_uuid")
        self.col_iocs.create_index([("to_ids",1),("timestamp",-1)])
        self.col_iocs.create_index("norm.host")
        self.col_iocs.create_index("norm.ip")

    # ---- MAIN pull (default 24h, exclude_imported=True)
    def pull(self, since: str = "24h", published: Optional[bool] = None,
             exclude_imported: bool = True, request_id: Optional[str] = None) -> dict:
        rid = request_id or "-"
        t0 = time.perf_counter(); now = datetime.now(timezone.utc)
        last = _since_to_dt(since, now).strftime("%Y-%m-%d %H:%M:%S")
        flt = {"controller":"events","last":last,"published":published}
        if exclude_imported and self.imported_tag: flt["tags"]=[f"!{self.imported_tag}"]

        misp = self._client()
        t1=time.perf_counter(); events = misp.search(**flt)
        log.info("pull:search rid=%s count=%d ms=%d", rid, len(events), int((time.perf_counter()-t1)*1000))

        ev_ops: List[UpdateOne]=[]; ioc_ops: List[UpdateOne]=[]
        for e in events:
            E=e["Event"]; ts=_to_dt(int(E["timestamp"]))
            ev_doc = {
                "event_id": int(E["id"]), "uuid": E["uuid"], "info": E.get("info"),
                "orgc": E.get("Orgc",{}).get("name"), "org": E.get("Org",{}).get("name"),
                "published": bool(E.get("published",False)),
                "attribute_count": int(E.get("attribute_count", len(E.get("Attribute",[])))),
                "timestamp": ts, "tags": [t["name"] for t in E.get("Tag", [])],
                "galaxies": _galaxies(E),
                "source": {"misp_url": self.url, "pulled_at": now}
            }
            ev_ops.append(UpdateOne({"uuid": ev_doc["uuid"]}, {"$set": ev_doc}, upsert=True))

            for a in E.get("Attribute", []) or []:
                A = {
                    "attr_id": int(a["id"]), "uuid": a["uuid"],
                    "event_id": int(E["id"]), "event_uuid": E["uuid"],
                    "category": a.get("category"), "type": a.get("type"), "value": a.get("value"),
                    "to_ids": bool(int(a.get("to_ids","0"))),
                    "timestamp": _to_dt(int(a["timestamp"])),
                    "tags": [t["name"] for t in a.get("Tag", [])],
                    "norm": _normalize(a.get("type"), a.get("value")),
                    "source": {"misp_url": self.url, "pulled_at": now},
                }
                left,right=_split_pipe(a.get("value","")); 
                if left or right: A["value_parts"]={"left":left,"right":right}
                ioc_ops.append(UpdateOne({"uuid": A["uuid"]}, {"$set": A}, upsert=True))

        if ev_ops: self.col_events.bulk_write(ev_ops, ordered=False)
        if ioc_ops: self.col_iocs.bulk_write(ioc_ops, ordered=False)

        # tag imported để lần sau tránh trùng
        tagged=0
        if self.imported_tag and events:
            try:
                for e in events:
                    euuid=e["Event"]["uuid"]
                    if not any(t.get("name")==self.imported_tag for t in e["Event"].get("Tag",[]) or []):
                        misp.tag(euuid, self.imported_tag, local=True); tagged += 1
            except Exception as te:
                log.warning("pull:tagging.failed rid=%s err=%s", rid, te)

        dur = int((time.perf_counter()-t0)*1000)
        log.info("pull:done rid=%s ev=%d ioc=%d tagged=%d ms=%d", rid, len(ev_ops), len(ioc_ops), tagged, dur)
        return {"ok": True, "since": since, "events_upserted": len(ev_ops), "iocs_upserted": len(ioc_ops),
                "events_tagged": tagged, "duration_ms": dur, "pulled_at": now.isoformat()}

    # ---- simple readers for dashboard
    def stats(self) -> dict:
        return {
            "events": self.col_events.estimated_document_count(),
            "iocs": self.col_iocs.estimated_document_count(),
            "iocs_to_ids": self.col_iocs.count_documents({"to_ids": True}),
            "last_event_ts": next(self.col_events.find().sort("timestamp",-1).limit(1), {}).get("timestamp")
        }

    def query_events(self, q: dict, limit: int = 50) -> List[dict]:
        return list(self.col_events.find(q).sort("timestamp",-1).limit(limit))

    def query_iocs(self, q: dict, limit: int = 100) -> List[dict]:
        return list(self.col_iocs.find(q).sort("timestamp",-1).limit(limit))

    def tag_event(self, event_uuid: str, tag: str, add: bool=True, local: bool=True) -> dict:
        if not tag: return {"ok": False, "error": "tag is required"}
        misp = self._client()
        try:
            if add:
                misp.tag(event_uuid, tag, local=local)
                self.col_events.update_one({"uuid": event_uuid}, {"$addToSet": {"tags": tag}})
            else:
                misp.untag(event_uuid, tag)
                self.col_events.update_one({"uuid": event_uuid}, {"$pull": {"tags": tag}})
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    def ping(self) -> dict:
        import requests
        url = f"{self.url}/users/view/me"
        verify = self.verify if self.url.startswith("https://") else False
        r = requests.get(url, headers={"Authorization": self.key}, timeout=10, verify=verify, allow_redirects=False)
        return {"ok": r.status_code == 200, "status": r.status_code, "url": url}