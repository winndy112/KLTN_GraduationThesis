from typing import List, Dict, Any

def parse_zeek_header(lines: List[str]) -> Dict[str, Any]:
    """Parses Zeek header lines to get fields and types."""
    fields = []
    types = []
    for line in lines:
        if line.startswith("#fields"):
            fields = line.strip().split()[1:]
        elif line.startswith("#types"):
            types = line.strip().split()[1:]
    return {"fields": fields, "types": types}

def parse_zeek_line(line: str, fields: List[str], types: List[str]) -> Dict[str, Any]:
    """Parses a single Zeek log line into a dictionary."""
    values = line.strip().split('\t')
    if len(values) != len(fields):
        return {}
    
    record = {}
    for i, field in enumerate(fields):
        val = values[i]
        if val == '-':
            record[field] = None
        else:
            # Basic type conversion
            t = types[i] if i < len(types) else 'string'
            if t == 'time' or t == 'double':
                try:
                    record[field] = float(val)
                except ValueError:
                    record[field] = val
            elif t == 'count' or t == 'int':
                try:
                    record[field] = int(val)
                except ValueError:
                    record[field] = val
            elif t == 'bool':
                record[field] = (val == 'T')
            else:
                record[field] = val
    return record
