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
        "addRecipeNutrition": "true",
        "number": 5,
    }

    recipes_list = []
    seen_ids = set()  # avoid duplicates

    try:
        for ing in ingredients:
            params["includeIngredients"] = ing.strip()
            response = requests.get(SPOONACULAR_URL, params=params)
            response.raise_for_status()
            results = response.json().get("results", [])

            for r in results:
                if r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    nutrients_list = r.get("nutrition", {}).get("nutrients", [])
                    calories = next((n["amount"] for n in nutrients_list if n["name"] == "Calories"), None)
                    protein = next((n["amount"] for n in nutrients_list if n["name"] == "Protein"), None)
                    fat = next((n["amount"] for n in nutrients_list if n["name"] == "Fat"), None)

                    recipes_list.append({
                        "title": r.get("title"),
                        "image": r.get("image"),
                        "url": r.get("sourceUrl"),
                        "nutrients": {"calories": calories, "protein": protein, "fat": fat},
                        "instructions": [s["step"] for s in r.get("analyzedInstructions", [{}])[0].get("steps", [])]
                    })

        return recipes_list

    except requests.RequestException as e:
        return {"error": str(e)}, 500
