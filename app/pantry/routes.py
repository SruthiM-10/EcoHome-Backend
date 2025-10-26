#app/pantry/routes.py

from fastapi import APIRouter
from app.db.schemas import RecipesInput
import requests
import re
import os


router = APIRouter(prefix="/pantry", tags=["pantry"])

@router.post("/recipes")
def recipes(body: RecipesInput):
    return {"hello"}
