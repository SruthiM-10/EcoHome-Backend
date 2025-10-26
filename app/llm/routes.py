#app/llm/routes.py

from fastapi import APIRouter
from app.db.schemas import ApplianceInput
import requests
from bs4 import BeautifulSoup
import re
import urllib.parse
from ddgs import DDGS
import time
import random
import serpapi
import os


router = APIRouter(prefix="/llm", tags=["llm"])

os.environ["SERP_API_KEY"] = "a44490072b649f025cfa40e7dbf1ea25"

@router.post("/getStats")
def getStats(body: ApplianceInput):
    listings = find_product_listings(body.appliance)
    return {"listings": listings}

def find_product_listings(query):
    """
    Searches DuckDuckGo for a query and returns URLs likely to be product listings.
    Free + no site restrictions.
    """

    listings = []

    url = "https://api.serpstack.com/search"
    params = {
        "access_key": os.getenv("SERP_API_KEY"),
        "query": query,
        "type": "shopping",
        "num": 30,  # grab a few more
    }
    BASE_HEADERS = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
    }
    r = requests.get(url, params=params, headers=BASE_HEADERS, timeout=20)
    if r.status_code != 200:
        return None
    j = r.json()
    results = j.get("shopping_results") or []

    print("Actual length of results: ", len(results))
    for page in results:
        url = page.get("url") or "product"
        bad_markers = "wiki|review|report|helpowl|guide|html|blog"
        product_like = re.compile(
            r"(product|/p/|/dp/|item|buy|shop|store|sku|model|specifications?|listing|best-rated|reviews)", re.I)

        if re.search(bad_markers, url):
            print("Found bad markers")
            continue
        if re.search(product_like, url):
            print('Very good!')
            print(url)
            listings.append({
                "title": page.get("title"),
                "url": url,
                "price": page.get("price"),
                "merchant": page.get("merchant"),
                "rating": page.get("rating"),
                "reviews": page.get("reviews")
            })
        print(url)

    return listings

# Example use
if __name__ == "__main__":
    query = "washing machine"
    listings = find_product_listings(query)

    if listings:
        print(f"Found {len(listings)} product listings.")
        for i, item in enumerate(listings[:5], 1):  # Print only first 5
            print(f"{i}. {item['title']}")
            print(f"   URL: {item['url']}")
            print(f"   Snippet: {item['price']}")
