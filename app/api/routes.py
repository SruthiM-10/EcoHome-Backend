#app/api/Thermostat

import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.models import Thermostat
from app.db.schemas import UserOverride
from app.db.database import get_db
from datetime import timedelta, datetime as dt
from app.utils.scheduler import schedule_override
import requests


router = APIRouter(prefix="/api", tags=["api"])

@router.post("/override_thermostat")
def override(body: UserOverride):
    try:
        away = body.away
        time = body.time
        id = body.id
        schedule_override(id, dt.utcnow(), dt.utcnow() + timedelta(hours=time), away)
        return {"message": "Data saved", "away": away, "time_away": time}
    except Exception as e:
        return {"error": str(e)}

@router.get("/sync_thermostat")
def sync_thermostat(id: int, db: Session = Depends(get_db)):
    try:
        row = db.query(Thermostat).filter(Thermostat.id == id).first()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        away = row.away
        last_end_time = row.last_end_time
        if away:
            lat, lon = os.getenv("LAT"), os.getenv("LON")
            outside_f = get_outdoor_temp_f(lat, lon, os.getenv("OWM_API_KEY"))
            # set_nest_temperature_f(
            #     os.getenv("NEST_DEVICE_NAME"), os.getenv("NEST_ACCESS_TOKEN"), outside_f
            # )
            return {"away": True, "message": f"Nest set to outside temp - {outside_f}. The next event will end on {last_end_time}."}
        else:
            return {"away": False, "message": "User appears to be home."}
    except Exception as e:
        return {"error": str(e)}

def get_outdoor_temp_f(lat: str, lon: str, api_key: str) -> float:
    """Return current outdoor temperature in °F using OpenWeatherMap."""
    url = (
        "https://api.openweathermap.org/data/2.5/weather?" f"lat={lat}&lon={lon}&appid={api_key}&units=imperial"
    )
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()["main"]["temp"]