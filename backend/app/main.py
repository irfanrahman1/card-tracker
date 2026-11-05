"""Card Tracker API entry point. Run with: uvicorn app.main:app --reload"""
import os
from urllib.parse import urlsplit

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import event

from . import models  # noqa: F401  (imported so the tables are registered)
from .auth import delete_expired
from .categories import CATEGORIES
from .database import IS_SQLITE, Base, SessionLocal, add_missing_columns, engine
from .routers import auth, cards, demo, insights, transactions

if IS_SQLITE:
    # SQLite ignores foreign keys (and ON DELETE rules) unless asked per connection.
    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")


# Create tables on startup. Fine for a small app; switch to Alembic if the schema grows.
Base.metadata.create_all(engine)
add_missing_columns()  # upgrade databases created by older versions
with SessionLocal() as _db:
    delete_expired(_db)  # old sessions and day-old demo accounts

app = FastAPI(title="Card Tracker")

# The website and the API are served from the same address (Vite forwards /api in
# development; one server does both in production), so no cross-site access (CORS)
# is allowed at all. Sites listed here may still send requests (comma-separated).
ALLOWED_ORIGINS = {o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()}


@app.middleware("http")
async def security(request: Request, call_next):
    # Block changes (POST/PUT/PATCH/DELETE) sent from other websites, on top of the
    # SameSite cookie, so a malicious page can't act on a logged-in visitor's behalf.
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin:
            same_host = urlsplit(origin).netloc == request.headers.get("host")
            if not same_host and origin not in ALLOWED_ORIGINS:
                return JSONResponse({"detail": "Cross-site request blocked"}, status_code=403)
    response = await call_next(request)
    # Standard protective headers.
    response.headers["X-Content-Type-Options"] = "nosniff"  # don't guess file types
    response.headers["X-Frame-Options"] = "DENY"  # can't be embedded in another site (clickjacking)
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"  # personal data isn't cached
    else:
        # The website may only load its own scripts and styles, and talk only to its own API.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000"  # HTTPS only from now on
    return response


app.include_router(auth.router)
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


# ---------- The website (production) ----------
# In production the built React app (frontend/dist) is copied to STATIC_DIR and served
# by this same server, so the website and API share one address. In development, Vite
# serves the website instead and this folder doesn't exist.
STATIC_DIR = Path(os.environ.get("STATIC_DIR", Path(__file__).resolve().parent.parent / "static"))

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def website(path: str):
        """Any non-API address loads the app (React handles the rest)."""
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        file = (STATIC_DIR / path).resolve()
        if path and file.is_file() and STATIC_DIR.resolve() in file.parents:
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")
