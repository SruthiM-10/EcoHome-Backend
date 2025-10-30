#app/api/routes.py

import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.models import Thermostat, User
from app.db.schemas import UserOverride, ThermostatDevice, TempInput
from app.db.database import get_db
from datetime import timedelta, datetime as dt
from app.api.scheduler import schedule_override
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
        energy_saved = row.energy_saved if row.energy_saved is not None else 0.0
        cost_saved = row.cost_saved if row.cost_saved is not None else 0.0
        if away:
            lat, lon = os.getenv("LAT"), os.getenv("LON")
            outside_f = get_outdoor_temp_f(lat, lon, os.getenv("OWM_API_KEY"))
            # set_nest_temperature_f(
            #     os.getenv("NEST_DEVICE_NAME"), os.getenv("NEST_ACCESS_TOKEN"), outside_f
            # )
            row.outside_temp = outside_f
            db.commit()
            db.refresh(row)
            #return {"away": True, "message": f"Nest should be set to outside temp - {outside_f}. The next event will end on {last_end_time}."}
            return {
                "away": True,
                "message": f"Nest should be set to outside temp - {outside_f}. The next event will end on {last_end_time}.",
                "energy_saved": energy_saved,  # Added
                "cost_saved": cost_saved  # Added
            }
        else:
            #return {"away": False, "message": "User appears to be home."}
            return {
                "away": False,
                "message": "User appears to be home.",
                "energy_saved": energy_saved,  # Added
                "cost_saved": cost_saved  # Added
            }
    except Exception as e:
        return {"error": str(e)}

@router.post("/add_thermostat")
def add_thermostat(body: ThermostatDevice, db: Session = Depends(get_db)):
    existing = db.query(Thermostat).filter(Thermostat.device_name == body.device_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Device already registered")
    device = Thermostat(id=body.id, device_name=body.device_name)
    db.add(device)
    db.commit()
    db.refresh(device)
    return {"message": "Registration successful."}

def get_thermostat_temp(full_device_name: str, access_token: str):
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
        raise HTTPException(status_code=response.status_code, detail=response.text)

def get_outdoor_temp_f(lat: str, lon: str, api_key: str) -> float:
    """Return current outdoor temperature in °F using OpenWeatherMap."""
    url = (
        "https://api.openweathermap.org/data/2.5/weather?" f"lat={lat}&lon={lon}&appid={api_key}&units=imperial"
    )
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()["main"]["temp"]

@router.post("/set_thermostat_temp")
def set_nest_temperature_c(body: TempInput, db: Session = Depends(get_db)):
    existing_Thermostat = db.query(Thermostat).filter(Thermostat.id == body.id).first()
    if not existing_Thermostat:
        raise HTTPException(status_code=400, detail="No device already registered under this id")

    device_id = existing_Thermostat.device_name

    existing_User = db.query(User).filter(User.id == body.id).first()
    if not existing_User:
        raise HTTPException(status_code=400, detail="ID cannot be found")
    access_token = existing_User.google_access_token

    # Construct the full device name
    full_device_name = f"enterprises/{Project_ID}/devices/{device_id}"
    #target_temp_c = existing_Thermostat.preheat_time  # e.g., 22°C
    target_temp_c = float(existing_Thermostat.preheat_time) if existing_Thermostat.preheat_time else None
    if target_temp_c is None:
        raise ValueError("Target temperature (preheat_time) is missing or invalid.")

    # current_temp = get_thermostat_temp(full_device_name, access_token)
    # current_temp = current_temp["traits"]["sdm.devices.traits.Temperature"]["ambientTemperatureCelsius"]
    current_temp_response = get_thermostat_temp(full_device_name, access_token)
    current_temp_c = current_temp_response["traits"]["sdm.devices.traits.Temperature"]["ambientTemperatureCelsius"]
    outdoor_temp_f = existing_Thermostat.outside_temp

    # energy_saved, cost_saved = estimate_energy_cost_savings(current_temp, target_temp_c, target_temp_c, 20, 0.15)
    if outdoor_temp_f is None:
        energy_saved = 0.0
        cost_saved = 0.0
    else:
        outdoor_temp_c = (outdoor_temp_f - 32) * 5 / 9
        energy_saved, cost_saved = estimate_energy_cost_savings(current_temp_c,target_temp_c,outdoor_temp_c,20,0.15)
    #existing_Thermostat.energy_saved = energy_saved
   # existing_Thermostat.cost_saved = cost_saved
    existing_Thermostat.energy_saved = float(energy_saved)
    existing_Thermostat.cost_saved = float(cost_saved)
    db.commit()
    db.refresh(existing_Thermostat)

    set_temp_url = f"https://smartdevicemanagement.googleapis.com/v1/{full_device_name}:executeCommand"
    payload = {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
        "params": {"heatCelsius": target_temp_c}
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    resp = requests.post(set_temp_url, headers=headers, json=payload)
    if resp.status_code == 200:
        return {"message": "Thermostat is now set successfully"}
    else:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

def estimate_energy_cost_savings(current_temp, new_temp, outdoor_temp, baseline_energy_kwh, price_per_kwh):
    delta_T = abs(current_temp - new_temp)
    baseline_delta_T = abs(current_temp - outdoor_temp)

    if baseline_delta_T == 0:
        return 0, 0

    energy_saved = (delta_T / baseline_delta_T) * baseline_energy_kwh
    cost_saved = energy_saved * price_per_kwh

    return energy_saved, cost_saved

@router.post("/get_saved_energy")
def get_saved_energy(body: TempInput, db: Session = Depends(get_db)):
    existing_Thermostat = db.query(Thermostat).filter(Thermostat.id == body.id).first()
    if not existing_Thermostat:
        raise HTTPException(status_code=400, detail="No device already registered under this id")

    #return {"energy": existing_Thermostat.energy_saved}
    return {"energy": existing_Thermostat.energy_saved or 0.0}

@router.post("/get_saved_cost")
def get_saved_cost(body: TempInput, db: Session = Depends(get_db)):
    existing_Thermostat = db.query(Thermostat).filter(Thermostat.id == body.id).first()
    if not existing_Thermostat:
        raise HTTPException(status_code=400, detail="No device already registered under this id")

    #return {"cost": existing_Thermostat.cost_saved}
    return {"cost": existing_Thermostat.cost_saved or 0.0}
