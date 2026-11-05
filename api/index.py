"""Vercel entry point: runs the FastAPI app from backend/app as a serverless function.

Vercel serves the built website (frontend/dist) from its CDN and sends every /api/...
request here (see vercel.json). Locally you don't need this file; use ./start.sh.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401  (Vercel looks for a variable named `app`)
