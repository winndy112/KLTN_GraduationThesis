import os
import gzip
import glob
from datetime import datetime
from typing import List, Dict, Any
from .config import ZEEK_LOG_DIR, CURRENT_LOG_DIR
from .zeek_parser import parse_zeek_header, parse_zeek_line

def read_file_segment(file_path: str, start_ts: float, end_ts: float, limit: int, cursor: float) -> List[Dict[str, Any]]:
    """
    Reads a Zeek log file and returns records matching the time range and cursor.
    """
    records = []
    try:
        if file_path.endswith('.gz'):
            opener = gzip.open
        else:
            opener = open
            
        with opener(file_path, 'rt', encoding='utf-8', errors='replace') as f:
            # Parse Header
            header_lines = []
            while True:
                pos = f.tell()
                line = f.readline()
                if not line: break
                if line.startswith('#'):
                    header_lines.append(line)
                else:
                    f.seek(pos)
                    break
            
            header = parse_zeek_header(header_lines)
            fields = header.get("fields", [])
            types = header.get("types", [])
            
            if not fields: return []
            
            try:
                ts_idx = fields.index('ts')
            except ValueError:
                return []

            # Scan lines
            for line in f:
                if line.startswith('#'): continue
                
                # Optimization: Check ts before full parse
                parts = line.split('\t', ts_idx + 2)
                if len(parts) <= ts_idx: continue
                
                try:
                    ts = float(parts[ts_idx])
                except ValueError:
                    continue
                
                if ts > cursor and start_ts <= ts <= end_ts:
                    rec = parse_zeek_line(line, fields, types)
                    if rec:
                        records.append(rec)
                        if len(records) >= limit:
                            break
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return records

def search_logs(mode: str, start_ts: float, end_ts: float, limit: int, cursor: float) -> List[Dict[str, Any]]:
    """
    Main entry point for log search.
    mode: 'live' (checks current logs) or 'history' (checks archived logs)
    """
    results = []
    
    if mode == 'live':
        # Check current/conn.log
        # TODO: Make log type configurable? Defaulting to conn.log
        target_file = os.path.join(CURRENT_LOG_DIR, "conn.log")
        if os.path.exists(target_file):
            results.extend(read_file_segment(target_file, start_ts, end_ts, limit, cursor))
            
    elif mode == 'history':
        # Check archived logs in ZEEK_LOG_DIR/YYYY-MM-DD/conn.log.gz
        # Naive implementation: iterate all date folders in range
        # For efficiency, we should calculate the date range and only check those folders.
        
        start_dt = datetime.fromtimestamp(start_ts)
        end_dt = datetime.fromtimestamp(end_ts)
        
        # Iterate days (simplified: just glob and filter for now to avoid complex date math imports if not needed)
        # A better way is to construct paths based on dates between start and end.
        
        # Let's assume we just look at the directories that match the date pattern
        # This is a placeholder for the full date iteration logic
        # In a real scenario, we'd iterate: current = start_dt; while current <= end_dt: ...
        
        from datetime import timedelta
        curr = start_dt
        while curr <= end_dt + timedelta(days=1): # +1 buffer
            date_str = curr.strftime("%Y-%m-%d")
            
            # Check compressed
            gz_path = os.path.join(ZEEK_LOG_DIR, date_str, "conn.log.gz")
            if os.path.exists(gz_path):
                results.extend(read_file_segment(gz_path, start_ts, end_ts, limit - len(results), cursor))
            
            # Check uncompressed (if any)
            log_path = os.path.join(ZEEK_LOG_DIR, date_str, "conn.log")
            if os.path.exists(log_path):
                 results.extend(read_file_segment(log_path, start_ts, end_ts, limit - len(results), cursor))
            
            if len(results) >= limit:
                break
            
            curr += timedelta(days=1)

    return results
