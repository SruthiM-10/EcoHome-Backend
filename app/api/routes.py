#app/api/routes.py

import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.models import Thermostat
from app.db.schemas import UserOverride, ThermostatDevice
from app.db.database import get_db
from datetime import timedelta, datetime as dt
from app.utils.scheduler import schedule_override
import requests

router = APIRouter(prefix="/api", tags=["api"])

Project_ID = os.getenv("DEVICE_ACCESS_PROJECT_ID")

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

@router.post("/add_thermostat")
def add_thermostat(body: ThermostatDevice, db: Session = Depends(get_db)):
    existing = db.query(Thermostat).filter(Thermostat.device_name == body.device_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Device already registered")
    device = ThermostatDevice(id=body.device_id, name=body.device_name)
    db.add(device)
    db.commit()
    db.refresh(device)
    return {"message": "Registration successful."}

def get_thermostat_temp(device_id: str, access_token: str):
    # Construct the full device name
    full_device_name = f"enterprises/{Project_ID}/devices/{device_id}"

    url = f"https://smartdevicemanagement.googleapis.com/v1/{full_device_name}"

    headers = {
        "Content-Type": "application/json",
        # The access token must be prepended with "Bearer " or "Token " as per OAuth 2.0 specs
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        # Handle API errors
        raise HTTPException(status_code=response.status_code, detail=response.text)

def get_outdoor_temp_f(lat: str, lon: str, api_key: str) -> float:
    """Return current outdoor temperature in °F using OpenWeatherMap."""
    url = (
        "https://api.openweathermap.org/data/2.5/weather?" f"lat={lat}&lon={lon}&appid={api_key}&units=imperial"
    )
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()["main"]["temp"]