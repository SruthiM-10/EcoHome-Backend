#app/pantry/routes.py

from fastapi import APIRouter
from app.db.schemas import RecipesInput
import requests
import re
import os

SPOONACULAR_API_KEY = "ed53ed3517484f159d2964f45cab8cf1"  # 🔑 Replace with your API key
SPOONACULAR_URL = "https://api.spoonacular.com/recipes/complexSearch"

router = APIRouter(prefix="/pantry", tags=["pantry"])

@router.post("/recipes")
def recipes(body: RecipesInput):
    ingredients = body.ingredients
    restrictions = body.restrictions

    params = {
        "apiKey": SPOONACULAR_API_KEY,
        "includeIngredients": ",".join(ingredients),
        "diet": ",".join(restrictions),
        "addRecipeInformation": "true",
        "number": 5,
    }

    try:
        response = requests.get(SPOONACULAR_URL, params=params)
        response.raise_for_status()
        results = response.json().get("results", [])

        recipes_list = []
        for r in results:
            recipes_list.append({
                "title": r.get("title"),
                "image": r.get("image"),
                "nutrients": r.get("nutrition", {}).get("nutrients", []),
                "instructions": [s["step"] for s in r.get("analyzedInstructions", [{}])[0].get("steps", [])],
            })

        return recipes_list

    except requests.RequestException as e:
        return {"error": str(e)}
