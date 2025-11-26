from fastapi import FastAPI, Request
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi.templating import Jinja2Templates
from app.database.mongo import db_sec, db_ioc
from app.database.collections import seed_sid_counter
from fastapi.staticfiles import StaticFiles
from fastapi import Request, Response
from datetime import datetime, timezone
from app.api import alerts, health, misp, rules, sensors
app = FastAPI()
# templates = Jinja2Templates(directory="./app/templates")
# app.mount("/static", StaticFiles(directory="./app/static"), name="static")

app.include_router(sensors.router)
app.include_router(rules.router)
app.include_router(alerts.router)
app.include_router(health.router)
app.include_router(misp.router)

@app.post("/admin/seed-sid")
def admin_seed_sid():
    v = seed_sid_counter(default_start=3_000_000)
    return {"ok": True, "seed_value": v, "next": v + 1}


    
# @app.get("/viewer")
# def alert_viewer(request: Request):
#     """
#     Trang viewer để xem và tìm kiếm alert
#     """
#     return templates.TemplateResponse("alerts_viewer.html", {"request": request})
    
# @app.get("/recent")
# def alert_recent(request: Request):
#     """
#     Trang viewer để xem và tìm kiếm alert
#     """
#     return templates.TemplateResponse("alerts.html", {"request": request})