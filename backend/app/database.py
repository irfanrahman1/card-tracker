"""Database setup: one SQLite file, one SQLAlchemy engine, one session per request."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Defaults to a local file next to where you start the server. Override with the
# DATABASE_URL environment variable (see .env.example).
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./card_tracker.db")

# check_same_thread=False lets FastAPI use the connection from its worker threads.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: open a session for the request and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
