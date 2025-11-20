from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx, asyncio

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])
