from sqlmodel import SQLModel, Field, create_engine, select, Session
from database import create_db_and_tables

class Cards(SQLModel, table=True):
    id: int = Field(primary_key=True)
    name: str | None = None
    maxLevel: int | None = None
    maxEvolutionLevel: int | None = None
    elixirCost: float | None = None
    rarity: str | None = None

engine = create_engine("postgresql://postgres:admin@localhost:5432/clashroyale")

create_db_and_tables()