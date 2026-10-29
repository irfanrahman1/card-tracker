"""Card Tracker API entry point. Run with: uvicorn app.main:app --reload"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import event

from . import models  # noqa: F401  (imported so the tables are registered)
from .categories import CATEGORIES
from .database import Base, add_missing_columns, engine
from .routers import cards, demo, insights, transactions


# SQLite ignores foreign keys (and ON DELETE rules) unless asked per connection.
@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, _record):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


# Create tables on startup. Fine for a small app; switch to Alembic if the schema grows.
Base.metadata.create_all(engine)
add_missing_columns()  # upgrade databases created by older versions

app = FastAPI(title="Card Tracker")

# Allow the React dev server to call the API from another port.
origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"]
)

app.include_router(cards.router)
app.include_router(transactions.router)
app.include_router(insights.router)
app.include_router(demo.router)


@app.get("/api/categories")
def list_categories():
    return CATEGORIES


@app.get("/api/health")
def health():
    return {"status": "ok"}
