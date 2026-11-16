"""The card catalog (catalog/cards.json): every card is filled in correctly and can be added."""
from fastapi.testclient import TestClient

from app.catalog import catalog_cards
from app.categories import CATEGORIES
from app.main import app


def test_every_card_is_filled_in_correctly():
    ids = [card["id"] for card in catalog_cards()]
    assert len(ids) == len(set(ids)), "two cards have the same id"
    for card in catalog_cards():
        assert card["name"] and card["issuer"] and card["source"], card["id"]
        assert card["reward_type"] in ("cash", "points"), card["id"]
        assert card["annual_fee"] >= 0 and card["base_rate"] > 0, card["id"]
        for rule in card["rules"]:
            assert rule["category"] in CATEGORIES, (card["id"], rule["category"])
            assert rule["rate"] >= card["base_rate"], (card["id"], rule)  # a rule never pays less than the base rate


def test_every_card_can_be_added_to_a_wallet():
    client = TestClient(app, base_url="http://localhost")
    r = client.post("/api/auth/signup", json={"email": "catalog@example.com", "password": "correct horse battery"})
    assert r.status_code == 201, r.text
    for card in catalog_cards():
        r = client.post(f"/api/cards/from-catalog/{card['id']}")
        assert r.status_code in (200, 201), (card["id"], r.text)


def test_new_cards_are_in_the_catalog():
    ids = {card["id"] for card in catalog_cards()}
    for new in ("chase-prime-visa", "citi-costco-anywhere", "wells-fargo-autograph",
                "capital-one-venture", "citi-strata-premier"):
        assert new in ids
