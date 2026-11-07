"""The PDF upload endpoints: preview first (saves nothing), then import."""
from fastapi.testclient import TestClient

from app.main import app

from .pdf_maker import make_pdf

STATEMENT = make_pdf([
    "Other Bank Rewards Card",
    "Previous Balance                                      $0.00",
    "New Balance                                           $69.70",
    "11/02/26  TRADER JOE'S #552  NEW YORK NY             $54.20",
    "11/05/26  STARBUCKS  NEW YORK NY                      $6.25",
    "11/06/26  NYCT PAYGO  NEW YORK NY                     $9.25",
])


def signup(email):
    client = TestClient(app, base_url="http://localhost")
    r = client.post("/api/auth/signup", json={"email": email, "password": "correct horse battery"})
    assert r.status_code == 201, r.text
    return client


def upload(client, path, **form):
    return client.post(path, files={"file": ("statement.pdf", STATEMENT, "application/pdf")}, data=form)


def test_preview_shows_rows_and_saves_nothing():
    client = signup("pdf-preview@example.com")
    r = upload(client, "/api/transactions/upload-pdf/preview")
    assert r.status_code == 200, r.text
    body = r.json()
    assert [row["merchant"] for row in body["rows"]] == ["TRADER JOE'S #552 NEW YORK NY", "STARBUCKS NEW YORK NY", "NYCT PAYGO NEW YORK NY"]
    assert [row["category"] for row in body["rows"]] == ["groceries", "food", "transportation"]
    assert body["totals_checked"] and body["warnings"] == []
    assert client.get("/api/transactions").json() == []  # nothing saved


def test_import_leaves_out_unticked_rows_and_skips_duplicates():
    client = signup("pdf-import@example.com")
    rows = upload(client, "/api/transactions/upload-pdf/preview").json()["rows"]
    starbucks = rows[1]["id"]

    r = upload(client, "/api/transactions/upload-pdf", leave_out=starbucks)
    assert r.json()["imported"] == 2
    assert sorted(t["merchant"] for t in client.get("/api/transactions").json()) == [
        "NYCT PAYGO NEW YORK NY", "TRADER JOE'S #552 NEW YORK NY"]

    # uploading it again: the preview marks the imported rows, and importing adds only Starbucks
    again = upload(client, "/api/transactions/upload-pdf/preview").json()["rows"]
    assert [row["already_imported"] for row in again] == [True, False, True]
    assert upload(client, "/api/transactions/upload-pdf").json()["imported"] == 1


def test_not_a_pdf():
    client = signup("pdf-bad@example.com")
    r = client.post("/api/transactions/upload-pdf/preview", files={"file": ("x.pdf", b"hello", "application/pdf")})
    assert r.status_code == 400 and r.json()["detail"] == "That file isn't a PDF."


def test_needs_login():
    client = TestClient(app, base_url="http://localhost")
    assert upload(client, "/api/transactions/upload-pdf/preview").status_code == 401
