"""The card catalog: popular cards with their reward rules, loaded from cards.json.

The data lives in a JSON file (not code) so updating a card's terms is a data
change anyone can review. Each card records when its terms were checked.
"""
import json
from functools import lru_cache
from pathlib import Path

CATALOG_FILE = Path(__file__).with_name("cards.json")


@lru_cache
def load_catalog() -> dict:
    with CATALOG_FILE.open() as f:
        return json.load(f)


def catalog_cards() -> list[dict]:
    return load_catalog()["cards"]


def find_card(catalog_id: str) -> dict | None:
    return next((c for c in catalog_cards() if c["id"] == catalog_id), None)


def display_name(spec: dict) -> str:
    """"American Express Gold Card", but "Apple Card" (not "Apple Apple Card")."""
    return spec["name"] if spec["name"].startswith(spec["issuer"]) else f"{spec['issuer']} {spec['name']}"
