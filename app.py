from typing import Optional, List
import requests
import pandas as pd
from sqlmodel import SQLModel, Field, Session, create_engine, select
from database import create_db_and_tables, engine, sqlite_url
from models import Cards, Players, Clans, ClanMembers, CardDeck, CardCollection, BattlePlayers, BattleLogs
from urllib.parse import quote

# --------- CONFIG ----------
API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6ImVjODA4NWEyLTA0YmEtNDU1ZC04N2U4LTg2NTI1MmRmMzY0NyIsImlhdCI6MTc2NDQ4NzM2Miwic3ViIjoiZGV2ZWxvcGVyL2IwNTIwMmVhLTM4ZjYtNjc1MC1iNjYyLTVkMDYzYmRmNDVhYyIsInNjb3BlcyI6WyJyb3lhbGUiXSwibGltaXRzIjpbeyJ0aWVyIjoiZGV2ZWxvcGVyL3NpbHZlciIsInR5cGUiOiJ0aHJvdHRsaW5nIn0seyJjaWRycyI6WyIxNTguNjIuNjIuMTk5Il0sInR5cGUiOiJjbGllbnQifV19.3L-CIOhUxhgVPsiXtt2v40DtECZvzSAwUBPPRl4eYjgOWm02puCp3Vn7ITRKcAsBhAONrcFrm4500b8_lKcfRg"  # replace with your Clash Royale API token
CARDS_URL = "https://api.clashroyale.com/v1/cards"
# BATTLELOGS_URL = F'https://api.clashroyale.com/v1/players/{quote(player_tag)}/battlelog'
# CLAN_URL = f"https://api.clashroyale.com/v1/clans/{quote(clan_tag)}" #Ex. tag:#R28V0GV0, get:https://api.clashroyale.com/v1/clans/%23R28V0GV0


# --------- FETCH API DATA -------------
# CARDS
def fetch_cards(api_token):
    headers = {"Authorization": f"Bearer {api_token}"}
    resp = requests.get(CARDS_URL, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    return data.get("items", [])

# PLAYERS
def fetch_player(api_token, player_tag):
    """Fetch a single player profile"""
    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"https://api.clashroyale.com/v1/players/{quote(player_tag)}"
    
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()

# BATTLELOGS
def fetch_battlelogs(api_token, player_tag):
    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"https://api.clashroyale.com/v1/players/{quote(player_tag)}/battlelog"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


# --------- FILTER/NORMALIZE EXCTRACTED DATA -------------
# CARDS FILTER
def normalize_card(item):
    # convert null values to None
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
        "max_level": null_if_missing_or_nan(item.get("maxLevel")),
        "max_evolution_level": null_if_missing_or_nan(item.get("maxEvolutionLevel")),
        "elixir_cost": null_if_missing_or_nan(item.get("elixirCost")),
        "rarity": item.get("rarity"),
    }

# PLAYERS FILTER
def normalize_player(data):
    return {
        "tag": data.get("tag"),
        "clan_tag": data.get("clan", {}).get("tag"),
        "player_name": data.get("name"),
        "exp_level": data.get("expLevel"),
        "trophies": data.get("trophies"),
        "best_trophies": data.get("bestTrophies"),
        "wins": data.get("wins"),
        "losses": data.get("losses"),
        "battle_counts": data.get("battleCount"),
        "favorite_card": data.get('currentFavouriteCard').get('id'),
    }

# PLAYER'S CURRENT DECK FILTER
def normalize_deck_cards(data, player_id):
    deck = data.get("currentDeck", [])
    records = []
    for i, card in enumerate(deck):
        records.append({
            "player_id": player_id,
            'player_tag':data.get('tag'),
            "card_name": card.get('name'),
            "card_id": card.get("id"),
            "level": card.get("level"),
            "star_level": card.get("starLevel", 0),
            "max_level": card.get("maxLevel", 0),
            "slot": i + 1
        })
    return records

# CARD COLLECTIONS FILTER
def normalize_collection_cards(data, player_id):
    """Extract full card collection"""
    cards = data.get("cards", [])
    records = []
    for card in cards:
        records.append({
            "player_id": player_id,
            "card_id": card.get("id"),
            "card_name": card.get("name"),
            "level": card.get("level"),
            "star_level": card.get("starLevel", 0),
            "evolution_level": card.get("evolutionLevel", 0),
            "count": card.get("count", 0)
        })
    return records

# BATTLELOGS FILTER
def normalize_battlelogs(data, player_id):
    battles = data  # it's already a list of battles
    records = []
    
    for battle in battles:
        opponent = battle.get("opponent", [{}])[0]
        player_clan = battle.get("clan", {}).get("tag", None)
        opponent_clan = opponent.get("clan", {}).get("tag", None)

        records.append({
            "player_id": player_id,
            "player_tag": battle.get("team", [{}])[0].get("tag"),
            "clan_tag": player_clan,
            "opponent_tag": opponent.get("tag"),
            "opponent_name": opponent.get("name"),
            "opponent_clan_tag": opponent_clan,
            "result": battle.get("team", [{}])[0].get("crowns", 0),  # crowns can help later for win/loss logic
            "battle_type": battle.get("type"),
            "utc_date": battle.get("battleTime")
        })

    return records


# --------- INSERT DATA TO DATABASE -------------
# INSERT CARDS
def insert_cards_to_db(records):
    with Session(engine) as session:
        for rec in records:
            card = Cards(**rec)
            session.merge(card)  
        session.commit()

# INSERT PLAYER
def insert_player_to_db(record: dict):
    """Upsert player profile into DB"""
    with Session(engine) as session:
        player = Players(**record) 
        session.merge(player)
        session.commit()

# INSERT PLAYER'S CURRENT DECK
def insert_deck_to_db(records):
    with Session(engine) as session:
        for rec in records:
            deck_card = CardDeck(
                player_id = rec["player_id"],
                player_tag = rec["player_tag"],
                card_name = rec["card_name"],
                card_id = rec["card_id"],
                level = rec["level"],
                star_level= rec["star_level"],
                max_level = rec["max_level"],
                slot = rec["slot"]
            )
            session.merge(deck_card)  # upsert
        session.commit()


# INSERT PLAYER'S CARD COLLECTION
def insert_card_collection_to_db(records):
    with Session(engine) as session:
        for rec in records:
            card = CardCollection(
                player_id = rec["player_id"],
                card_id = rec["card_id"],
                card_name = rec["card_name"],
                level = rec["level"],
                star_level = rec["star_level"],
                evolution_level = rec["evolution_level"],
                count = rec["count"]
            )
            session.merge(card)
        session.commit()

create_db_and_tables()


player_tag = "#RUQ0JU2P"  # your target tag
player_data = fetch_player(API_TOKEN, player_tag)
player_record = normalize_player(player_data)

with Session(engine) as session:
    player = Players(**player_record)
    session.add(player)  
    session.commit()        
    session.refresh(player) 
    player_id = player.id   

deck_records = normalize_deck_cards(player_data, player_id)
collection_records = normalize_collection_cards(player_data, player_id)

insert_deck_to_db(deck_records)
insert_card_collection_to_db(collection_records)