from typing import Optional, List
import requests
import pandas as pd
from datetime import datetime
from sqlmodel import Session, select
from database import create_db_and_tables, engine
from models import Cards, Players, Clans, CardDeck, CardCollection, BattleLogs
from urllib.parse import quote

# --------- CONFIG ----------
API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6ImVjODA4NWEyLTA0YmEtNDU1ZC04N2U4LTg2NTI1MmRmMzY0NyIsImlhdCI6MTc2NDQ4NzM2Miwic3ViIjoiZGV2ZWxvcGVyL2IwNTIwMmVhLTM4ZjYtNjc1MC1iNjYyLTVkMDYzYmRmNDVhYyIsInNjb3BlcyI6WyJyb3lhbGUiXSwibGltaXRzIjpbeyJ0aWVyIjoiZGV2ZWxvcGVyL3NpbHZlciIsInR5cGUiOiJ0aHJvdHRsaW5nIn0seyJjaWRycyI6WyIxNTguNjIuNjIuMTk5Il0sInR5cGUiOiJjbGllbnQifV19.3L-CIOhUxhgVPsiXtt2v40DtECZvzSAwUBPPRl4eYjgOWm02puCp3Vn7ITRKcAsBhAONrcFrm4500b8_lKcfRg"
CARDS_URL = "https://api.clashroyale.com/v1/cards"


# --------- FETCH API DATA -------------
def fetch_cards(api_token):
    """Fetch all cards data"""
    headers = {"Authorization": f"Bearer {api_token}"}
    resp = requests.get(CARDS_URL, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return data.get("items", [])


def fetch_player(api_token, player_tag):
    """Fetch a single player profile"""
    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"https://api.clashroyale.com/v1/players/{quote(player_tag)}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def fetch_battlelogs(api_token, player_tag):
    """Fetch player battle logs"""
    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"https://api.clashroyale.com/v1/players/{quote(player_tag)}/battlelog"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def fetch_clan(api_token, clan_tag):
    """Fetch clan information"""
    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"https://api.clashroyale.com/v1/clans/{quote(clan_tag)}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
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


def insert_player_to_db(record: dict):
    """Upsert player profile into DB"""
    with Session(engine) as session:
        player = Players(**record)
        session.merge(player)
        session.commit()


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


def insert_battlelogs_to_db(records):
    """Insert battle logs"""
    with Session(engine) as session:
        for rec in records:
            battle = BattleLogs(**rec)
            session.add(battle)
        session.commit()


def insert_clan_to_db(record: dict):
    """Insert or update clan"""
    with Session(engine) as session:
        clan = Clans(**record)
        session.merge(clan)
        session.commit()


def get_player_id_by_tag(player_tag: str) -> Optional[int]:
    """Get player ID from database by tag"""
    with Session(engine) as session:
        statement = select(Players).where(Players.tag == player_tag)
        player = session.exec(statement).first()
        return player.id if player else None


# --------- MAIN EXECUTION -------------
if __name__ == "__main__":
    create_db_and_tables()

    player_tag = "#VC0PYJ9LJ"
    print(f"Fetching player data for {player_tag}...")
    player_data = fetch_player(API_TOKEN, player_tag)
    player_record = normalize_player(player_data)
    
    with Session(engine) as session:
        player = Players(**player_record)
        session.add(player)
        session.commit()
        session.refresh(player)
        player_id = player.id
    
    print("Processing deck and collection...")
    deck_records = normalize_deck_cards(player_data, player_id)
    collection_records = normalize_collection_cards(player_data, player_id)
    insert_deck_to_db(deck_records)
    insert_card_collection_to_db(collection_records)
    print()
    
    print(f"Fetching battle logs for {player_tag}...")
    battlelogs_data = fetch_battlelogs(API_TOKEN, player_tag)
    battlelog_records = normalize_battlelogs(battlelogs_data, player_id, player_tag)
    insert_battlelogs_to_db(battlelog_records)
    print()
    
    if player_record.get('clan_tag'):
        clan_tag = player_record['clan_tag']
        print(f"Fetching clan data for {clan_tag}...")
        clan_data = fetch_clan(API_TOKEN, clan_tag)
        clan_record = normalize_clan(clan_data)
        insert_clan_to_db(clan_record)
    else:
        print("Player is not in a clan")