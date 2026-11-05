"""Database setup: one SQLite file, one SQLAlchemy engine, one session per request."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Defaults to a local file next to where you start the server. Override with the
# DATABASE_URL environment variable (see .env.example).
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./card_tracker.db")

# Hosts often hand out "postgres://..." URLs; SQLAlchemy wants a driver name.
if DATABASE_URL.startswith(("postgres://", "postgresql://")):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL.split("://", 1)[1]

IS_SQLITE = DATABASE_URL.startswith("sqlite")
# check_same_thread=False lets FastAPI use a SQLite connection from its worker threads.
# pool_pre_ping reconnects if a hosted Postgres closed an idle connection.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    pool_pre_ping=not IS_SQLITE,
)
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


def add_missing_columns() -> None:
    """Tiny migration: add columns that newer versions of models.py define.

    create_all() makes missing *tables* but never changes existing ones, so a
    database from an older version would be missing new columns. This adds them
    (SQLite ALTER TABLE ADD COLUMN), keeping all existing data.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                kind = column.type.compile(engine.dialect)
                default = column.default.arg if column.default is not None and not callable(column.default.arg) else None
                sql = f'ALTER TABLE {table.name} ADD COLUMN {column.name} {kind}'
                if default is not None:
                    sql += f" DEFAULT {default!r}" if isinstance(default, str) else f" DEFAULT {default}"
                conn.execute(text(sql))
