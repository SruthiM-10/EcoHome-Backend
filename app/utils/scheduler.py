import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from app.db.models import Thermostat
import re
from app.db.database import get_db
from app.utils.calendar_utils import get_upcoming_events
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

# THERMOSTAT_API_URL = "http://localhost:3000/setMode"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler")

scheduler = BackgroundScheduler()

def preheat(event_summary):
    logger.info(f"\n[🔥] Preheating for event: {event_summary}\n")
    # try:
        # response = requests.post(THERMOSTAT_API_URL, json={"mode": "home"})
    # TODO
    logger.info(f"\n[✅] Thermostat response: ...\n")
    # except Exception as e:
    #     logger.error(f"[❌] Failed to call thermostat API: {e}")

def reset(id, away, time_away, end_time= datetime.utcnow(), db: Session = Depends(get_db)):
    row = db.query(Thermostat).filter(Thermostat.id == id).first() # later add based on device name
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    user_override = row.user_override
    if not user_override:
        row.away = away
        row.time_away = time_away
        row.user_override = user_override
        row.last_end_time = end_time
        db.commit()
        if not away:
            sync_and_schedule(id)

def override(id, away, time_away, event_end = False, end_time= datetime.utcnow(), db: Session = Depends(get_db)):
    row = db.query(Thermostat).filter(Thermostat.id == id).first() # later add based on device name
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    row.away = away
    row.time_away = time_away
    row.user_override = not event_end
    row.last_end_time = end_time.isoformat()
    db.commit()
    if event_end:
        sync_and_schedule(id)

def schedule_event_preheat(id, start_time, end_time, title):
    preheat_time = end_time - timedelta(minutes=30) # TODO: calculate time delta with different function with energy calculations

    scheduler.add_job(reset, DateTrigger(run_date= start_time), args=[id, True, end_time - start_time, end_time])


    scheduler.add_job(preheat, DateTrigger(run_date= preheat_time), args=[title])
    scheduler.add_job(reset, DateTrigger(run_date= end_time), args=[id, False, 0])
    logger.info(f"\n[🕒] Scheduled preheat for '{title}' at {preheat_time}\n")

def schedule_override(id, start_time, end_time, away):
    time_away = int((end_time - start_time).total_seconds() // 60)
    preheat_time = end_time - timedelta(minutes=min(30, time_away))  # TODO: calculate time delta with different function with energy calculations

    override(away, time_away, end_time)
    if preheat_time != end_time and away:
        scheduler.add_job(preheat, DateTrigger(run_date=preheat_time), args=['Override'])
    scheduler.add_job(override, DateTrigger(run_date=end_time), args=[id, False, 0, True])
    logger.info(f"\n[🕒] Scheduled preheat for 'Override' at {preheat_time}\n")

def sync_and_schedule(id):
    logger.info("\n[📆] Syncing calendar and scheduling preheat jobs...\n")
    try:
        address = "23 Linden Dr, Santa Clara, CA 95050"
        home_keywords = re.split(r"[,\s]+", address.strip())
        upcoming_events = get_upcoming_events(home_keywords=home_keywords)
        if len(upcoming_events) >= 2:
            event = upcoming_events[0]
            schedule_event_preheat(id, event.get('start_time'), event.get('end_time'), event.get('event')['summary'])

    except Exception as e:
        logger.error(f"\n[❌] Calendar sync failed: {e}\n")

def start_scheduler():
    logger.info("\n[🚀] Starting scheduler...\n")
    scheduler.start()