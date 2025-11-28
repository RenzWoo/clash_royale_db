from fastapi import FastAPI, HTTPException
from sqlmodel import Session, select
import requests
import pandas as pd
from database import engine, create_db_and_tables
from models import Cards

# --------- CONFIG ----------
API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjE2NTRjYmNkLWE5YmYtNDE0Yi1iOWI1LThiOWVjNTRlNjY2MCIsImlhdCI6MTc2NDMzMDU1Niwic3ViIjoiZGV2ZWxvcGVyL2IwNTIwMmVhLTM4ZjYtNjc1MC1iNjYyLTVkMDYzYmRmNDVhYyIsInNjb3BlcyI6WyJyb3lhbGUiXSwibGltaXRzIjpbeyJ0aWVyIjoiZGV2ZWxvcGVyL3NpbHZlciIsInR5cGUiOiJ0aHJvdHRsaW5nIn0seyJjaWRycyI6WyIxNTguNjIuNjMuMzUiXSwidHlwZSI6ImNsaWVudCJ9XX0.KRaXXQZgIuXQnSkAEnyiFccWpfLkNvPatX2rfquwJ8uYihOMeH9s9Y_ENvHrafxH19hmXayqdoDSNHJeuK9GpA"
URL = "https://api.clashroyale.com/v1/cards"

app = FastAPI()

@app.on_event("startup")
def on_startup():
    create_db_and_tables()


# --------- FETCH CARDS DATA ----------
def fetch_cards(api_token: str):
    headers = {"Authorization": f"Bearer {api_token}"}
    resp = requests.get(URL, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to fetch cards from API")
    data = resp.json()
    return data.get("items", [])

def normalize_card(item: dict) -> dict:
    def null_if_missing_or_nan(val):
        if val is None:
            return None
        try:
            if pd.isna(val):
                return None
        except Exception:
            pass
        return val

    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "maxLevel": null_if_missing_or_nan(item.get("maxLevel")),
        "maxEvolutionLevel": null_if_missing_or_nan(item.get("maxEvolutionLevel")),
        "elixirCost": null_if_missing_or_nan(item.get("elixirCost")),
        "rarity": item.get("rarity"),
    }

def insert_to_db(records):
    with Session(engine) as session:
        for rec in records:
            card = Cards(**rec)
            session.merge(card)  # merge = upsert by PK
        session.commit()
    return len(records)


# --------- ENDPOINT ----------
@app.get("/cards")
def get_cards():
    items = fetch_cards(API_TOKEN)
    normalized = [normalize_card(item) for item in items]
    count = insert_to_db(normalized)
    return {"message": f"Upserted {count} cards into the database.", "cards": normalized}


@app.get("/")
def root():
    return {"message": "Welcome to Clash Royale API"}