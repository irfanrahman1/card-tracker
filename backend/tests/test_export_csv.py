"""Downloading your purchases as a CSV file."""
import csv
import io

from fastapi.testclient import TestClient

from app.main import app


def signup(email):
    client = TestClient(app, base_url="http://localhost")
    r = client.post("/api/auth/signup", json={"email": email, "password": "correct horse battery"})
    assert r.status_code == 201, r.text
    return client


def add(client, merchant, amount, day="2026-10-01", card_id=None):
    r = client.post("/api/transactions", json={"date": day, "merchant": merchant, "amount": amount, "card_id": card_id})
    assert r.status_code == 201, r.text


def export(client):
    r = client.get("/api/transactions/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    return list(csv.DictReader(io.StringIO(r.text)))


def test_export_has_every_purchase_oldest_first():
    client = signup("export@example.com")
    card = client.post("/api/cards", json={"name": "My Card", "base_rate": 1}).json()["id"]
    add(client, "Trader Joe's", 54.20, "2026-10-05", card)
    add(client, "Starbucks", 6.25, "2026-10-01")
    rows = export(client)
    assert [(r["Date"], r["Merchant"], r["Amount"], r["Card"]) for r in rows] == [
        ("2026-10-01", "Starbucks", "6.25", ""),
        ("2026-10-05", "Trader Joe's", "54.20", "My Card"),
    ]
    assert rows[1]["Category"] == "groceries"


def test_text_that_looks_like_a_formula_is_made_safe():
    client = signup("export-formula@example.com")
    add(client, '=HYPERLINK("http://evil.example")', 5)
    assert export(client)[0]["Merchant"] == "'=HYPERLINK(\"http://evil.example\")"


def test_exported_file_can_be_imported_again():
    owner = signup("export-roundtrip@example.com")
    add(owner, "Trader Joe's", 54.20, "2026-10-05")
    add(owner, "Starbucks", 6.25, "2026-10-01")
    file = owner.get("/api/transactions/export").content

    other = signup("export-roundtrip-2@example.com")
    r = other.post("/api/transactions/upload", files={"file": ("purchases.csv", file, "text/csv")})
    assert r.json()["imported"] == 2
    assert sorted(t["merchant"] for t in other.get("/api/transactions").json()) == ["Starbucks", "Trader Joe's"]


def test_only_your_own_purchases():
    owner = signup("export-owner@example.com")
    add(owner, "Secret Store", 10)
    stranger = signup("export-stranger@example.com")
    assert export(stranger) == []


def test_needs_login():
    assert TestClient(app, base_url="http://localhost").get("/api/transactions/export").status_code == 401
