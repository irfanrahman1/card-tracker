"""Undoing an upload: every purchase from that one file is deleted, nothing else."""
from fastapi.testclient import TestClient

from app.main import app

from .pdf_maker import make_pdf

CSV = b"""Date,Description,Amount
10/01/2026,TRADER JOE'S #552,54.20
10/02/2026,STARBUCKS,6.25
"""

PDF = make_pdf([
    "Previous Balance $0.00",
    "New Balance $9.25",
    "11/06/26  NYCT PAYGO  NEW YORK NY      $9.25",
])


def signup(email):
    client = TestClient(app, base_url="http://localhost")
    r = client.post("/api/auth/signup", json={"email": email, "password": "correct horse battery"})
    assert r.status_code == 201, r.text
    return client


def upload_csv(client, name="october.csv"):
    return client.post("/api/transactions/upload", files={"file": (name, CSV, "text/csv")})


def merchants(client):
    return sorted(t["merchant"] for t in client.get("/api/transactions").json())


def test_undo_deletes_only_that_upload():
    client = signup("undo@example.com")
    client.post("/api/transactions", json={"date": "2026-10-03", "merchant": "Typed By Hand", "amount": 5})
    upload_csv(client)
    client.post("/api/transactions/upload-pdf", files={"file": ("nov.pdf", PDF, "application/pdf")})

    imports = client.get("/api/transactions/imports").json()
    assert [(i["filename"], i["source"], i["count"]) for i in imports] == [("nov.pdf", "pdf", 1), ("october.csv", "csv", 2)]

    r = client.delete(f"/api/transactions/imports/{imports[1]['id']}")  # undo the CSV
    assert r.json() == {"deleted": 2}
    assert merchants(client) == ["NYCT PAYGO NEW YORK NY", "Typed By Hand"]
    assert [i["filename"] for i in client.get("/api/transactions/imports").json()] == ["nov.pdf"]


def test_upload_with_nothing_new_is_not_listed():
    client = signup("undo-dupes@example.com")
    upload_csv(client)
    upload_csv(client, "same-file-again.csv")  # all duplicates, adds nothing
    assert [i["filename"] for i in client.get("/api/transactions/imports").json()] == ["october.csv"]


def test_upload_disappears_when_its_purchases_are_deleted_by_hand():
    client = signup("undo-by-hand@example.com")
    upload_csv(client)
    for t in client.get("/api/transactions").json():
        client.delete(f"/api/transactions/{t['id']}")
    assert client.get("/api/transactions/imports").json() == []


def test_cannot_undo_someone_elses_upload():
    owner = signup("undo-owner@example.com")
    upload_csv(owner)
    import_id = owner.get("/api/transactions/imports").json()[0]["id"]

    stranger = signup("undo-stranger@example.com")
    assert stranger.delete(f"/api/transactions/imports/{import_id}").status_code == 404
    assert len(owner.get("/api/transactions").json()) == 2  # still there
