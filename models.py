from sqlmodel import SQLModel, Field, create_engine, select, Session, Relationship
from database import create_db_and_tables
from typing import List, Optional
from datetime import datetime

# --------- CARDS TABLE -----------
class Cards(SQLModel, table=True):
    id: int = Field(primary_key=True)
    name: str | None = None
    max_level: int | None = None
    max_evolution_level: int | None = None
    elixir_cost: float | None = None
    rarity: str | None = None


# --------- PLAYERS TABLE -----------
class Players(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tag: str | None = Field(default=None, unique=True)
    clan_tag: str | None = None
    player_name: str
    exp_level: int
    trophies: int 
    best_trophies: int
    wins: int
    losses: int
    battle_counts: int
    favorite_card: str

    deck_cards: List["CardDeck"] = Relationship(back_populates="player")
    collection_cards: List["CardCollection"] = Relationship(back_populates="player")
    battles: List["BattlePlayers"] = Relationship(back_populates="player")


# -------- PLAYER CARDS TABLES ------------

# Current deck
class CardDeck(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="players.id")
    card_id: int = Field(foreign_key="cards.id")
    level: int
    is_support: bool = Field(default=False)
    slot: int = Field(ge=1, le=8)

    player: "Players" = Relationship(back_populates="deck_cards")
    card: "Cards" = Relationship()

# All cards collection
class CardCollection(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="players.id")
    card_id: int = Field(foreign_key="cards.id")
    level: int
    star_level: Optional[int] = Field(default=0, ge=0)
    evolution_level: Optional[int] = Field(default=0, ge=0)
    count: Optional[int] = Field(default=0, ge=0)

    player: "Players" = Relationship(back_populates="collection_cards")
    card: "Cards" = Relationship()


# ---------- BATTLELOGS TABLES -----------
class BattleLogs(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    battle_time: datetime
    type: str
    arena_id: int
    arena_name: str
    game_mode_id: int
    game_mode_name: str
    deck_selection: str
    is_ladder_tournament: bool = False
    is_hosted_match: bool = False

    players: List["BattlePlayers"] = Relationship(back_populates="battle")



class BattlePlayers(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    battle_id: int = Field(foreign_key="battlelogs.id")
    player_id: int = Field(foreign_key="players.id")
    tag: str
    name: str
    starting_trophies: int
    trophy_change: int
    crowns: int
    elixir_leaked: float=Field(default=0.0)
    result: str = Field(default="")

    player: "Players" = Relationship(back_populates="battles")
    battle: "BattleLogs" = Relationship(back_populates="players")
    cards: List["BattleCards"] = Relationship(back_populates="battle_player")


class BattleCards(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    battle_player_id: int = Field(foreign_key="battleplayers.id")
    card_id: int = Field(foreign_key = "cards.id")
    level: int
    star_level: Optional[int] = None
    is_support: bool = False

    battle_player: "BattlePlayers" = Relationship(back_populates="cards")


# ---------- CLAN TABLES -----------
class Clans(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tag: str = Field(unique=True)
    name: str
    type: str
    description: str
    badge_id: int
    clan_score: int
    clan_war_trophies: int
    required_trophies: int
    donations_per_week: int
    members: int

    clan_members: List["ClanMembers"] = Relationship(back_populates="clan")


class ClanMembers(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    clan_id: int = Field(foreign_key="clans.id")
    player_tag: str
    name: str
    role: str
    exp_level: int
    trophies: int
    clan_rank: int
    previous_clan_rank: int
    donations: int
    donations_received: int
    clan_chest_points: int
    last_seen: str  # raw string for now

    clan: "Clans" = Relationship(back_populates="clan_members")

