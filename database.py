from sqlmodel import SQLModel, create_engine

postgres_url = "postgresql://postgres:admin@localhost:5432/clashroyale"
sqlite_url = "sqlite:///CRdatabase.db"
engine = create_engine(sqlite_url)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
