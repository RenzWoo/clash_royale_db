from typing import Optional, List
from fastapi import FastAPI, HTTPException
from sqlmodel import Session, select
import requests
import pandas as pd
from datetime import datetime
from contextlib import asynccontextmanager
from database import engine, create_db_and_tables
from models import Cards, Players, Clans, CardDeck, CardCollection, BattleLogs
from urllib.parse import quote


# --------- CONFIG ----------
API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjU5OTVhYzNhLWFlMzgtNGU2NS04ZTJlLTE1YTYxZDFhNDQ5MyIsImlhdCI6MTc2NDU3MzI2OCwic3ViIjoiZGV2ZWxvcGVyL2IwNTIwMmVhLTM4ZjYtNjc1MC1iNjYyLTVkMDYzYmRmNDVhYyIsInNjb3BlcyI6WyJyb3lhbGUiXSwibGltaXRzIjpbeyJ0aWVyIjoiZGV2ZWxvcGVyL3NpbHZlciIsInR5cGUiOiJ0aHJvdHRsaW5nIn0seyJjaWRycyI6WyIxNTguNjIuNjIuMTY2Il0sInR5cGUiOiJjbGllbnQifV19.69tVSMKi9z-8FidwGW-X9ONBBW3DpeINJvPqvG3EqaqTw1uWtQXLaMSAFVivmfimCt1Mq7u1z5SNuNWylrgRNw"
CARDS_URL = "https://api.clashroyale.com/v1/cards"

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)


# --------- FETCH API DATA -------------
def fetch_cards(api_token):
    """Fetch all cards data"""
    headers = {"Authorization": f"Bearer {api_token}"}
    resp = requests.get(CARDS_URL, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to fetch cards from API")
    data = resp.json()
    return data.get("items", [])


def fetch_player(api_token, player_tag):
    """Fetch a single player profile"""
    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"https://api.clashroyale.com/v1/players/{quote(player_tag)}"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Failed to fetch player {player_tag}")
    return resp.json()


def fetch_battlelogs(api_token, player_tag):
    """Fetch player battle logs"""
    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"https://api.clashroyale.com/v1/players/{quote(player_tag)}/battlelog"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Failed to fetch battle logs for {player_tag}")
    return resp.json()


def fetch_clan(api_token, clan_tag):
    """Fetch clan information"""
    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"https://api.clashroyale.com/v1/clans/{quote(clan_tag)}"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Failed to fetch clan {clan_tag}")
    return resp.json()


# --------- FILTER/NORMALIZE EXTRACTED DATA -------------
def normalize_card(item):
    """Convert null values to None"""
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


def normalize_player(data):
    """Normalize player data"""
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
        "favorite_card": data.get('currentFavouriteCard', {}).get('name', 'Unknown'),
    }


def normalize_deck_cards(data, player_id):
    """Normalize player's current deck"""
    deck = data.get("currentDeck", [])
    records = []
    for i, card in enumerate(deck):
        records.append({
            "player_id": player_id,
            'player_tag': data.get('tag'),
            "card_name": card.get('name'),
            "card_id": card.get("id"),
            "level": card.get("level"),
            "star_level": card.get("starLevel", 0),
            "max_level": card.get("maxLevel", 0),
            "slot": i + 1
        })
    return records


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


def normalize_battlelogs(battles, player_id, player_tag):
    """Normalize battle log data"""
    records = []
    
    for battle in battles:
        # Find the team data for the player
        team_data = None
        opponent_data = None
        
        # Battle can have team and opponent arrays
        team_list = battle.get("team", [])
        opponent_list = battle.get("opponent", [])
        
        # Find player's data in team
        for member in team_list:
            if member.get("tag") == player_tag:
                team_data = member
                break
        
        # Get opponent data
        if opponent_list:
            opponent_data = opponent_list[0]
        
        if not team_data:
            continue  # Skip if player data not found
        
        # Determine battle result
        player_crowns = team_data.get("crowns", 0)
        opponent_crowns = opponent_data.get("crowns", 0) if opponent_data else 0
        
        if player_crowns > opponent_crowns:
            result = "win"
        elif player_crowns < opponent_crowns:
            result = "loss"
        else:
            result = "draw"
        
        # Parse battle time (format: 20251130T131519.000Z)
        battle_time_str = battle.get("battleTime")
        battle_time = datetime.strptime(battle_time_str, "%Y%m%dT%H%M%S.%fZ")
        
        records.append({
            "player_id": player_id,
            "player_tag": player_tag,
            "battle_time": battle_time,
            "type": battle.get("type"),
            "arena_id": battle.get("arena", {}).get("id"),
            "game_mode_id": battle.get("gameMode", {}).get("id"),
            "game_mode_name": battle.get("gameMode", {}).get("name"),
            "starting_trophies": team_data.get("startingTrophies", 0),
            "trophy_change": team_data.get("trophyChange", 0),
            "crowns": player_crowns,
            "result": result,
            "elixir_leaked": team_data.get("elixirLeaked", 0.0)
        })
    
    return records


def normalize_clan(data):
    """Normalize clan data"""
    return {
        "tag": data.get("tag"),
        "name": data.get("name"),
        "type": data.get("type"),
        "description": data.get("description", ""),
        "badge_id": data.get("badgeId"),
        "clan_score": data.get("clanScore"),
        "clan_war_trophies": data.get("clanWarTrophies"),
        "required_trophies": data.get("requiredTrophies"),
        "donations_per_week": data.get("donationsPerWeek"),
        "members": data.get("members")
    }


# --------- INSERT DATA TO DATABASE -------------
def insert_cards_to_db(records):
    """Insert or update cards"""
    with Session(engine) as session:
        for rec in records:
            card = Cards(**rec)
            session.merge(card)
        session.commit()
    return len(records)


def insert_player_to_db(record: dict):
    """Upsert player profile into DB"""
    with Session(engine) as session:
        # Check if player exists
        statement = select(Players).where(Players.tag == record['tag'])
        existing_player = session.exec(statement).first()
        
        if existing_player:
            # Update existing player
            for key, value in record.items():
                setattr(existing_player, key, value)
            session.add(existing_player)
            session.commit()
            session.refresh(existing_player)
            return existing_player.id
        else:
            # Create new player
            player = Players(**record)
            session.add(player)
            session.commit()
            session.refresh(player)
            return player.id


def insert_deck_to_db(records):
    """Insert player's current deck"""
    with Session(engine) as session:
        # Delete existing deck cards for this player
        if records:
            player_id = records[0]["player_id"]
            statement = select(CardDeck).where(CardDeck.player_id == player_id)
            existing_cards = session.exec(statement).all()
            for card in existing_cards:
                session.delete(card)
        
        # Insert new deck
        for rec in records:
            deck_card = CardDeck(**rec)
            session.add(deck_card)
        session.commit()
    return len(records)


def insert_card_collection_to_db(records):
    """Insert player's card collection"""
    with Session(engine) as session:
        # Delete existing collection for this player
        if records:
            player_id = records[0]["player_id"]
            statement = select(CardCollection).where(CardCollection.player_id == player_id)
            existing_cards = session.exec(statement).all()
            for card in existing_cards:
                session.delete(card)
        
        # Insert new collection
        for rec in records:
            card = CardCollection(**rec)
            session.add(card)
        session.commit()
    return len(records)


def insert_battlelogs_to_db(records):
    """Insert battle logs"""
    with Session(engine) as session:
        for rec in records:
            battle = BattleLogs(**rec)
            session.add(battle)
        session.commit()
    return len(records)


def insert_clan_to_db(record: dict):
    """Insert or update clan"""
    with Session(engine) as session:
        clan = Clans(**record)
        session.merge(clan)
        session.commit()
        return clan.tag


# --------- ENDPOINTS -------------

@app.get("/")
def root():
    return {"message": "Welcome to Clash Royale API"}


# --------- DATABASE READ ENDPOINTS -------------

@app.get("/db/cards")
def get_all_cards_from_db():
    """Get all cards from database"""
    with Session(engine) as session:
        statement = select(Cards)
        cards = session.exec(statement).all()
        return {"count": len(cards), "cards": cards}


@app.get("/db/players")
def get_all_players_from_db():
    """Get all players from database"""
    with Session(engine) as session:
        statement = select(Players)
        players = session.exec(statement).all()
        return {"count": len(players), "players": players}


@app.get("/db/player/{player_tag}")
def get_player_from_db(player_tag: str):
    """Get specific player from database"""
    with Session(engine) as session:
        statement = select(Players).where(Players.tag == player_tag)
        player = session.exec(statement).first()
        if not player:
            raise HTTPException(status_code=404, detail=f"Player {player_tag} not found")
        return player


@app.get("/db/player/{player_tag}/deck")
def get_player_deck_from_db(player_tag: str):
    """Get player's current deck from database"""
    with Session(engine) as session:
        statement = select(Players).where(Players.tag == player_tag)
        player = session.exec(statement).first()
        if not player:
            raise HTTPException(status_code=404, detail=f"Player {player_tag} not found")
        
        deck_statement = select(CardDeck).where(CardDeck.player_id == player.id).order_by(CardDeck.slot)
        deck = session.exec(deck_statement).all()
        return {"player_tag": player_tag, "player_name": player.player_name, "deck": deck}


@app.get("/db/player/{player_tag}/collection")
def get_player_collection_from_db(player_tag: str):
    """Get player's card collection from database"""
    with Session(engine) as session:
        statement = select(Players).where(Players.tag == player_tag)
        player = session.exec(statement).first()
        if not player:
            raise HTTPException(status_code=404, detail=f"Player {player_tag} not found")
        
        collection_statement = select(CardCollection).where(CardCollection.player_id == player.id)
        collection = session.exec(collection_statement).all()
        return {"player_tag": player_tag, "player_name": player.player_name, "count": len(collection), "collection": collection}


@app.get("/db/player/{player_tag}/battles")
def get_player_battles_from_db(player_tag: str, limit: int = 25):
    """Get player's battle logs from database"""
    with Session(engine) as session:
        statement = select(Players).where(Players.tag == player_tag)
        player = session.exec(statement).first()
        if not player:
            raise HTTPException(status_code=404, detail=f"Player {player_tag} not found")
        
        battle_statement = (
            select(BattleLogs)
            .where(BattleLogs.player_id == player.id)
            .order_by(BattleLogs.battle_time.desc())
            .limit(limit)
        )
        battles = session.exec(battle_statement).all()
        return {"player_tag": player_tag, "player_name": player.player_name, "count": len(battles), "battles": battles}


@app.get("/db/clans")
def get_all_clans_from_db():
    """Get all clans from database"""
    with Session(engine) as session:
        statement = select(Clans)
        clans = session.exec(statement).all()
        return {"count": len(clans), "clans": clans}


@app.get("/db/clan/{clan_tag}")
def get_clan_from_db(clan_tag: str):
    """Get specific clan from database"""
    with Session(engine) as session:
        statement = select(Clans).where(Clans.tag == clan_tag)
        clan = session.exec(statement).first()
        if not clan:
            raise HTTPException(status_code=404, detail=f"Clan {clan_tag} not found")
        return clan


# --------- API SYNC ENDPOINTS -------------

@app.get("/cards")
def get_cards():
    """Fetch and store all cards from Clash Royale API"""
    items = fetch_cards(API_TOKEN)
    normalized = [normalize_card(item) for item in items]
    count = insert_cards_to_db(normalized)
    return {
        "message": f"Upserted {count} cards into the database",
        "count": count
    }


@app.get("/player/{player_tag}")
def sync_player(player_tag: str):
    """
    Fetch and sync player data including profile, deck, and card collection
    Example: /player/%23RUQ0JU2P (note: # must be URL encoded as %23)
    """
    # Fetch player data
    player_data = fetch_player(API_TOKEN, player_tag)
    player_record = normalize_player(player_data)
    
    # Insert player and get ID
    player_id = insert_player_to_db(player_record)
    
    # Insert deck and collection
    deck_records = normalize_deck_cards(player_data, player_id)
    collection_records = normalize_collection_cards(player_data, player_id)
    
    deck_count = insert_deck_to_db(deck_records)
    collection_count = insert_card_collection_to_db(collection_records)
    
    return {
        "message": f"Synced player {player_record['player_name']}",
        "player_tag": player_tag,
        "player_name": player_record['player_name'],
        "deck_cards": deck_count,
        "collection_cards": collection_count
    }


@app.get("/player/{player_tag}/battlelogs")
def sync_battlelogs(player_tag: str):
    """
    Fetch and sync battle logs for a player
    Example: /player/%23RUQ0JU2P/battlelogs
    """
    # Get player ID from database
    with Session(engine) as session:
        statement = select(Players).where(Players.tag == player_tag)
        player = session.exec(statement).first()
        if not player:
            raise HTTPException(status_code=404, detail=f"Player {player_tag} not found in database. Sync player first.")
        player_id = player.id
    
    # Fetch and insert battle logs
    battlelogs_data = fetch_battlelogs(API_TOKEN, player_tag)
    battlelog_records = normalize_battlelogs(battlelogs_data, player_id, player_tag)
    count = insert_battlelogs_to_db(battlelog_records)
    
    return {
        "message": f"Synced {count} battle logs for player {player_tag}",
        "count": count
    }


@app.get("/clan/{clan_tag}")
def sync_clan(clan_tag: str):
    """
    Fetch and sync clan data
    Example: /clan/%232YC0RG29J
    """
    clan_data = fetch_clan(API_TOKEN, clan_tag)
    clan_record = normalize_clan(clan_data)
    clan_tag = insert_clan_to_db(clan_record)
    
    return {
        "message": f"Synced clan {clan_record['name']}",
        "clan_tag": clan_tag,
        "clan_name": clan_record['name'],
        "members": clan_record['members']
    }


@app.get("/sync-all/{player_tag}")
def sync_all_player_data(player_tag: str):
    """
    Sync everything for a player: profile, deck, collection, battle logs, and clan
    Example: /sync-all/%23RUQ0JU2P
    """
    results = {}
    
    # 1. Sync player
    player_data = fetch_player(API_TOKEN, player_tag)
    player_record = normalize_player(player_data)
    player_id = insert_player_to_db(player_record)
    
    # 2. Sync deck and collection
    deck_records = normalize_deck_cards(player_data, player_id)
    collection_records = normalize_collection_cards(player_data, player_id)
    
    results['player_name'] = player_record['player_name']
    results['deck_cards'] = insert_deck_to_db(deck_records)
    results['collection_cards'] = insert_card_collection_to_db(collection_records)
    
    # 3. Sync battle logs
    try:
        battlelogs_data = fetch_battlelogs(API_TOKEN, player_tag)
        battlelog_records = normalize_battlelogs(battlelogs_data, player_id, player_tag)
        results['battle_logs'] = insert_battlelogs_to_db(battlelog_records)
    except Exception as e:
        results['battle_logs'] = f"Failed: {str(e)}"
    
    # 4. Sync clan (if player is in one)
    if player_record.get('clan_tag'):
        try:
            clan_data = fetch_clan(API_TOKEN, player_record['clan_tag'])
            clan_record = normalize_clan(clan_data)
            insert_clan_to_db(clan_record)
            results['clan_name'] = clan_record['name']
        except Exception as e:
            results['clan'] = f"Failed: {str(e)}"
    else:
        results['clan'] = "Player not in a clan"
    
    return {
        "message": f"Synced all data for {player_record['player_name']}",
        "results": results
    }