#app/llm/routes.py

import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.models import Thermostat
from app.db.schemas import UserOverride
from app.db.database import get_db
from datetime import timedelta, datetime as dt
from app.utils.scheduler import schedule_override
import requests


router = APIRouter(prefix="/llm", tags=["llm"])