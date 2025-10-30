#app/llm/routes.py

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.db.schemas import ApplianceInput
import requests
import numpy as np
import pandas as pd
from app.llm.scraping import try_selenium
from app.llm.data_processing import extract_features, data_cleaning, compare_features, clean_features, fill_url
import re

import os
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Listing
import pickle
import difflib

router = APIRouter(prefix="/llm", tags=["llm"])

os.environ["SERP_API_KEY"] = "a44490072b649f025cfa40e7dbf1ea25"

class FeaturesItem(BaseModel):
    energy: str
    durability: str
    quality: str
    repairability: str
    recyclability: str
    otherResourceUse: str
    compatibility: str
    policyAlignment: str

@router.post("/startGeneratingListings")
def startGeneratingListings(background_tasks: BackgroundTasks, body: ApplianceInput):
    background_tasks.add_task(generateListings, body)
    return {"status": "Successfully started to generate listings!"}

def generateListings(body: ApplianceInput, db: Session = Depends(get_db)):
    existing = db.query(Listing).filter(Listing.appliance == body.appliance).first()
    if existing:
        raise HTTPException(status_code=400, detail="Appliance already generated")

    listings = find_product_listings(body.appliance)
    listings2 = get_features(listings)
    listings3 = sort_listings(listings2)
    final_listings = final_processing(listings3)

    # with ("final_listings.pkl", "rb") as f:
    #     pickled_bytes = f.read()

    listing = Listing(appliance=body.appliance, data=pickle.dumps(final_listings))
    db.add(listing)
    db.commit()
    db.refresh(listing)

    return {"message": "Listing successfully added."}

@router.post("/getListings")
def getListings(body: ApplianceInput, db: Session = Depends(get_db)):
    all_rows = db.query(Listing).all()
    appliance_names = [row.appliance for row in all_rows]

    closest_matches = difflib.get_close_matches(body.appliance, appliance_names, n=1, cutoff=0.8)
    similar_rows = [row for row in all_rows if row.appliance in closest_matches]

    # existing = db.query(Listing).filter(Listing.appliance == body.appliance).first()
    if not similar_rows:
        raise HTTPException(status_code=400, detail="Appliance has not yet been generated")

    obj = pickle.loads(similar_rows[0].data)
    if hasattr(obj, "to_dict"):
        obj = obj.to_dict(orient="records")  # list of dicts

    return obj

def find_product_listings(query):
    listings = []

    url = "https://api.serpstack.com/search"
    params = {
        "access_key": os.getenv("SERP_API_KEY"),
        "query": query,
        "type": "shopping",
        "location": "San Jose, California, United States",
        "num": 10,  # grab a few more
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
            r"(product|/p/|/dp/|item|buy|shop|store|sku|model|specifications?|listing|best-rated)", re.I)

        if re.search(bad_markers, url):
            continue
        if re.search(product_like, url):
            title_str = page.get("title")
            truncated_title = ""
            if title_str:
                end_index = min(len(title_str) // 2, 30)
                truncated_title = title_str[:end_index]
            listings.append({
                "title": truncated_title,
                "info": {
                    "url": url,
                    "price": page.get("price"),
                    "seller": page.get("seller"),
                    "rating": page.get("rating"),
                    "reviews": page.get("reviews")
                }
            })
        print(url)

    return listings

def get_features(listings):
    total_features = []
    count = 0
    BASE_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        "Accept-Language": "en-US,en;q=0.9",
    }
    url = "https://api.serpstack.com/search"

    for listing in listings:
        listing["original_index"] = count
        listing["score"] = 0.0
        count += 1

        params = {
            "access_key": os.getenv("SERP_API_KEY"),
            "query": listing.get("title"),
            "location": "San Jose, California, United States",
            "num": 1,  # grab a few more
        }

        r = requests.get(url, params=params, headers=BASE_HEADERS, timeout=20)
        if r.status_code != 200:
            continue

        j = r.json()
        results = j.get("organic_results") or []
        final_url = ""
        for result in results:
            link = result.get('url')
            bad_markers = "wiki|review|report|helpowl|guide|html|blog"
            product_like = re.compile(
                r"(product|/p/|/dp/|item|sku)", re.I)

            if re.search(bad_markers, link):
                continue
            if re.search(product_like, link):
                final_url = link
                break

        all_text = ""

        if final_url == "":
            continue

        listing["info"]["url"] = final_url
        # try:
        #     response = requests.get(final_url, headers=BASE_HEADERS, timeout=(5, 10))
        #
        #     if response.status_code == 200:
        #         html_string = response.text
        #         soup = BeautifulSoup(html_string, 'html.parser')
        #         visible_text_string = soup.get_text()
        #         all_text = visible_text_string
        #     else:
        #         print(f"Requests got status {response.status_code} for {final_url}. Trying Selenium.")
        #
        # except requests.exceptions.RequestException as e:
        #     # This catches Timeout, ConnectionError, etc.
        #     print(f"Requests error ({e}) for {final_url}. Trying Selenium.")

        selenium_text = try_selenium(BASE_HEADERS, final_url)
        if selenium_text:
            all_text = selenium_text
        else:
            print(f"Selenium failed for {final_url}")

        if all_text:
            clean_text = "\n".join(line.strip() for line in all_text.split() if line.strip())
            final_text = data_cleaning(clean_text)

            features = extract_features(final_text)

            listing["text"] = final_text
            listing["features"] = features

        else:
            print(f"Failed to retrieve content for: {final_url}")
            listing["features"] = []

    return listings

def sort_listings(listings):

    def condense_features(listing):

        if pd.isna(listing["features"]):
            return listing
        print(listing["features"])
        listing["features"] = eval(listing["features"])
        total_features_list = pd.DataFrame([feature_item.model_dump() for feature_item in listing["features"]])
        condensed_features_list = {}
        for feature in total_features_list.columns:
            total_info = "\n".join(total_features_list[feature])
            condensed_features_list[feature] = total_info
        listing["features"] = condensed_features_list

        return listing

    listings = listings.apply(condense_features, axis=1)
    listings["price"] = listings["info"].apply(lambda info: eval(info).get("price"))
    all_features = list(listings["features"].iloc[0].keys())
    all_features.append("price")
    for feature in all_features:
        metric = feature
        text = ""
        count = 1
        for _, listing in listings.iterrows():
            text += f"\n---------\nAppliance {count}\n-----------\n"
            count += 1
            if not pd.isna(listing["features"]) and not pd.isna(listing["features"].get(feature)):
                text += listing["features"].get(feature)
        results = compare_features(metric, text)
        for result in results[0]:
            result = result.model_dump()
            listings.loc[result.get("originalIndex") - 1, "score"] += result.get("rank")

    sorted_listings = listings.sort_values(by="score", ascending=False)
    return sorted_listings

def final_processing(listings):
    final_listings = []
    listings.dropna(subset=["features"], inplace=True)
    listings["features"] = listings["features"].apply(lambda x: np.nan if len(x) <= 5 else x)
    listings.dropna(subset=["features"], inplace=True)

    for _, listing in listings.iterrows():
        all_features = list(eval(listings["features"].iloc[0]).keys())
        listing["features"] = eval(listing["features"])
        listing["info"] = eval(listing["info"])
        for feature in all_features:
            print(listing["features"])
            print(listing["info"])
            listing["info"][feature] = clean_features(metric= feature, text= listing["features"][feature])[0].get('snippet')
        final_listings.append({
            "title": listing["title"],
            "info": listing["info"]
        })
    return final_listings

def unit_test(query):
    listings = find_product_listings(query)

    if listings:
        print(f"Found {len(listings)} product listings.")
        for i, item in enumerate(listings[:5], 1):  # Print only first 5
            print(f"{i}. {item['title']}")

    listing = get_features(listings)
    listing_df = pd.DataFrame(listing)
    listing_df.to_csv("listing.csv", index=False)

    listings = pd.read_csv("listing.csv")
    sorted_listing = sort_listings(listings)
    sorted_listing.to_csv("sorted_listing.csv", index=False)

    sorted_listings = pd.read_csv("sorted_listing.csv")
    final_listing = pd.DataFrame(final_processing(sorted_listings))
    final_listing.to_pickle("final_listings.pkl")

    # with open ("/Users/sruthi/PycharmProjects/EcoHome-Backend/app/llm/final_listings.pkl", "rb") as f:
    #     current_listings = pickle.load(f)
    #
    # def test(row):
    #     print("Started - ", row["title"])
    #     row["info"]["url"] = fill_url(row["title"])
    #     print("New url: ", row["info"]["url"])
    #     return row["info"]
    # current_listings["info"] = current_listings.apply(test, axis= 1)
    # current_listings.to_pickle("final_listings2.pkl")