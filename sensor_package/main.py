from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
from . import log_reader
from .config import HOST, PORT

app = FastAPI(title="Sensor Log Search API")

class LogQueryResponse(BaseModel):
    data: List[Dict[str, Any]]
    next_cursor: float
    count: int

@app.get("/api/v1/logs/search", response_model=LogQueryResponse)
async def search_logs(
    mode: str = Query(..., regex="^(live|history)$"),
    start_ts: float = 0,
    end_ts: float = float('inf'),
    limit: int = 100,
    cursor: float = 0
):
    """
    Search Zeek logs.
    - mode: 'live' (current logs) or 'history' (archived logs)
    - start_ts, end_ts: Time range
    - limit: Max records
    - cursor: Return records with ts > cursor
    """
    logs = log_reader.search_logs(mode, start_ts, end_ts, limit, cursor)
    
    # Calculate next cursor
    next_cursor = cursor
    if logs:
        # Assuming logs are sorted or we find the max ts
        # Zeek logs are usually time-ordered.
        max_ts = max(l.get('ts', 0) for l in logs)
        next_cursor = max(cursor, max_ts)
        
    return {
        "data": logs,
        "next_cursor": next_cursor,
        "count": len(logs)
    }

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
