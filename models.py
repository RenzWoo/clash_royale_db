from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional
from datetime import datetime

# --------- CARDS TABLE -----------
class Cards(SQLModel, table=True):
    __tablename__ = "cards"
    
    id: int = Field(primary_key=True)
    name: Optional[str] = None
    max_level: Optional[int] = None
    max_evolution_level: Optional[int] = None
    elixir_cost: Optional[float] = None
    rarity: Optional[str] = None

    # Relationships
    deck_cards: List["CardDeck"] = Relationship(back_populates="card")
    collection_cards: List["CardCollection"] = Relationship(back_populates="card")


# --------- PLAYERS TABLE -----------
class Players(SQLModel, table=True):
    __tablename__ = "players"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    tag: str = Field(unique=True, index=True)
    clan_tag: Optional[str] = Field(default=None, index=True)
    player_name: str
    exp_level: int
    trophies: int 
    best_trophies: int
    wins: int
    losses: int
    battle_counts: int
    favorite_card: str

    # Relationships
    deck_cards: List["CardDeck"] = Relationship(back_populates="player")
    collection_cards: List["CardCollection"] = Relationship(back_populates="player")
    battle_logs: List["BattleLogs"] = Relationship(back_populates="player")


# -------- PLAYER CARDS TABLES ------------

# Current deck
class CardDeck(SQLModel, table=True):
    __tablename__ = "card_deck"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="players.id", index=True)
    player_tag: str = Field(index=True)
    card_name: str
    card_id: int = Field(foreign_key="cards.id", index=True)
    level: int
    star_level: int
    max_level: int
    slot: int = Field(ge=1, le=8)

    # Relationships
    player: "Players" = Relationship(back_populates="deck_cards")
    card: "Cards" = Relationship(back_populates="deck_cards")


# All cards collection
class CardCollection(SQLModel, table=True):
    __tablename__ = "card_collection"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="players.id", index=True)
    card_id: int = Field(foreign_key="cards.id", index=True)
    card_name: str
    level: int
    star_level: Optional[int] = Field(default=0, ge=0)
    evolution_level: Optional[int] = Field(default=0, ge=0)
    count: Optional[int] = Field(default=0, ge=0)

    # Relationships
    player: "Players" = Relationship(back_populates="collection_cards")
    card: "Cards" = Relationship(back_populates="collection_cards")


# ---------- BATTLELOGS TABLES -----------
class BattleLogs(SQLModel, table=True):
    __tablename__ = "battle_logs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    battle_time: datetime = Field(index=True)
    type: str
    arena_id: int
    game_mode_id: int
    game_mode_name: str
    player_id: int = Field(foreign_key="players.id", index=True)
    player_tag: str = Field(index=True)
    starting_trophies: int
    trophy_change: int
    crowns: int
    result: str  # win/loss/draw
    elixir_leaked: float

    # Relationships
    player: "Players" = Relationship(back_populates="battle_logs")


# ---------- CLAN TABLES -----------
class Clans(SQLModel, table=True):
    __tablename__ = "clans"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    tag: str = Field(unique=True, index=True)
    name: str
    type: str
    description: str
    badge_id: int
    clan_score: int
    clan_war_trophies: int
    required_trophies: int
    donations_per_week: int
    members: int