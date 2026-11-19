"""Is each card worth its annual fee? Rewards from your purchases, plus perks, minus the fee."""
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app


def signup(email):
    client = TestClient(app, base_url="http://localhost")
    r = client.post("/api/auth/signup", json={"email": email, "password": "correct horse battery"})
    assert r.status_code == 201, r.text
    return client


def add_card(client, **fields):
    card = {"name": "Test Card", "base_rate": 1, "reward_type": "cash", "annual_fee": 0, "credits_value": 0,
            "rules": [{"category": "food", "rate": 4}], **fields}
    r = client.post("/api/cards", json=card)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def buy(client, card_id, amount, days_ago=10, merchant="Some Restaurant", category="food"):
    day = (date.today() - timedelta(days=days_ago)).isoformat()
    r = client.post("/api/transactions", json={"date": day, "merchant": merchant, "amount": amount,
                                               "category": category, "card_id": card_id})
    assert r.status_code == 201, r.text


def worth(client, card_id):
    return next(w for w in client.get("/api/cards/worth").json() if w["card_id"] == card_id)


def test_one_month_of_purchases_is_estimated_for_a_year():
    client = signup("worth-estimate@example.com")
    card = add_card(client, annual_fee=95)
    buy(client, card, 100)  # 4% on food = $4 this month -> about $48 a year
    w = worth(client, card)
    assert w["months"] == 1 and w["yearly_rewards"] == 48.0
    assert w["net"] == 48.0 - 95  # costs more than it earns


def test_perks_count_toward_the_fee():
    client = signup("worth-perks@example.com")
    card = add_card(client, annual_fee=95, credits_value=100)
    buy(client, card, 100)
    assert worth(client, card)["net"] == 48.0 + 100 - 95


def test_card_with_no_purchases():
    client = signup("worth-empty@example.com")
    card = add_card(client, annual_fee=95)
    w = worth(client, card)
    assert w["months"] == 0 and w["yearly_rewards"] == 0 and w["net"] == -95


def test_purchases_older_than_a_year_are_left_out():
    client = signup("worth-old@example.com")
    card = add_card(client)
    buy(client, card, 100, days_ago=400)
    assert worth(client, card)["months"] == 0


def test_only_your_own_cards():
    owner = signup("worth-owner@example.com")
    add_card(owner)
    stranger = signup("worth-stranger@example.com")
    assert stranger.get("/api/cards/worth").json() == []
