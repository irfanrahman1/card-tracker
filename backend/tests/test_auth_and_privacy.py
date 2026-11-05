"""Accounts and privacy: logins work, and nobody can see or change anyone else's data."""
import pytest
from fastapi.testclient import TestClient

from app import auth, models
from app.database import SessionLocal
from app.main import app

PASSWORD = "correct horse battery"


def new_client():
    # The test client's "browser": keeps its own cookies, like a separate person.
    return TestClient(app, base_url="http://localhost")


def signup(email):
    client = new_client()
    r = client.post("/api/auth/signup", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return client


@pytest.fixture(autouse=True)
def fresh_limiter():
    with SessionLocal() as db:
        db.query(models.FailedAttempt).delete()
        db.commit()


def test_signup_login_logout():
    client = signup("ana@example.com")
    assert client.get("/api/auth/me").json()["email"] == "ana@example.com"
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    r = client.post("/api/auth/login", json={"email": "ANA@example.com ", "password": PASSWORD})
    assert r.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_session_cookie_is_httponly_and_samesite():
    r = new_client().post("/api/auth/signup", json={"email": "cookie@example.com", "password": PASSWORD})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_password_is_hashed_not_stored():
    signup("hash@example.com")
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="hash@example.com").one()
        assert PASSWORD not in user.password_hash and user.password_hash.startswith("$argon2")


def test_wrong_password_and_unknown_email_get_the_same_answer():
    signup("same@example.com")
    a = new_client().post("/api/auth/login", json={"email": "same@example.com", "password": "wrong password!!"})
    b = new_client().post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong password!!"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_weak_passwords_are_refused():
    r = new_client().post("/api/auth/signup", json={"email": "weak@example.com", "password": "short"})
    assert r.status_code == 400


def test_data_needs_login():
    client = new_client()
    for path in ["/api/cards", "/api/transactions", "/api/summary"]:
        assert client.get(path).status_code == 401, path


def test_users_cannot_see_or_change_each_others_data():
    alice, bob = signup("alice@example.com"), signup("bob@example.com")
    card = alice.post("/api/cards/from-catalog/amex-gold").json()
    tx = alice.post("/api/transactions", json={"date": "2026-10-01", "merchant": "Joe's Pizza",
                                               "amount": 20, "card_id": card["id"]}).json()
    # Bob sees nothing of Alice's...
    assert bob.get("/api/cards").json() == []
    assert bob.get("/api/transactions").json() == []
    assert bob.get("/api/summary").json()["total"] == 0
    # ...and can't touch her card or purchase, even knowing their ids.
    assert bob.put(f"/api/cards/{card['id']}", json={"name": "hacked"}).status_code == 404
    assert bob.delete(f"/api/cards/{card['id']}").status_code == 404
    assert bob.patch(f"/api/transactions/{tx['id']}", json={"category": "other"}).status_code == 404
    assert bob.delete(f"/api/transactions/{tx['id']}").status_code == 404
    # ...or attach his purchases to her card.
    r = bob.post("/api/transactions", json={"date": "2026-10-01", "merchant": "X", "amount": 5, "card_id": card["id"]})
    assert r.status_code == 404
    # Bob's "clear all" doesn't touch Alice.
    bob.post("/api/demo/clear")
    assert len(alice.get("/api/transactions").json()) == 1


def test_repeated_failed_logins_get_blocked():
    signup("target@example.com")
    attacker = new_client()
    for _ in range(5):
        attacker.post("/api/auth/login", json={"email": "target@example.com", "password": "guess guess guess"})
    r = attacker.post("/api/auth/login", json={"email": "target@example.com", "password": PASSWORD})
    assert r.status_code == 429  # blocked, even with the right password, until it cools down


def test_changes_from_other_websites_are_blocked():
    client = signup("csrf@example.com")
    r = client.post("/api/demo/clear", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_delete_account_removes_everything():
    client = signup("leaving@example.com")
    client.post("/api/demo/load")
    assert client.post("/api/auth/delete-account", json={"password": "wrong password!!"}).status_code == 401
    assert client.post("/api/auth/delete-account", json={"password": PASSWORD}).status_code == 204
    with SessionLocal() as db:
        assert db.query(models.User).filter_by(email="leaving@example.com").count() == 0
        assert db.query(models.Card).filter(models.Card.user_id.is_(None)).count() == 0
    assert client.get("/api/auth/me").status_code == 401


def test_demo_account_has_sample_data():
    client = new_client()
    r = client.post("/api/auth/demo")
    assert r.status_code == 201 and r.json()["is_demo"]
    assert len(client.get("/api/cards").json()) == 4
    assert len(client.get("/api/transactions").json()) > 50


def test_faked_forwarded_for_header_does_not_dodge_the_limit():
    signup("spoof@example.com")
    attacker = new_client()
    for i in range(20):  # the per-network limit, spread over many emails
        attacker.post("/api/auth/login", headers={"X-Forwarded-For": f"10.0.0.{i}"},
                      json={"email": f"someone-{i}@example.com", "password": "guess guess guess"})
    # Same real address, new fake header and a different email: still blocked by IP.
    r = attacker.post("/api/auth/login", headers={"X-Forwarded-For": "10.9.9.9"},
                      json={"email": "spoof@example.com", "password": PASSWORD})
    assert r.status_code == 429


def reset_link_token(capsys):
    """The email isn't sent in tests (no SMTP); it's printed. Pull the token out of it."""
    out = capsys.readouterr().out
    return out.split("?reset=")[1].split()[0]


def test_forgot_password_flow(capsys):
    signup("forgetful@example.com")
    client = new_client()
    r = client.post("/api/auth/forgot-password", json={"email": "forgetful@example.com"})
    assert r.status_code == 200
    token = reset_link_token(capsys)
    r = client.post("/api/auth/reset-password", json={"token": token, "new_password": "a brand new password"})
    assert r.status_code == 200 and client.get("/api/auth/me").status_code == 200
    # Old password no longer works; new one does.
    assert new_client().post("/api/auth/login", json={"email": "forgetful@example.com", "password": PASSWORD}).status_code == 401
    assert new_client().post("/api/auth/login", json={"email": "forgetful@example.com", "password": "a brand new password"}).status_code == 200
    # The link works only once.
    again = new_client().post("/api/auth/reset-password", json={"token": token, "new_password": "another new password"})
    assert again.status_code == 400


def test_forgot_password_same_answer_for_unknown_email(capsys):
    signup("known@example.com")
    a = new_client().post("/api/auth/forgot-password", json={"email": "known@example.com"})
    b = new_client().post("/api/auth/forgot-password", json={"email": "unknown@example.com"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()


def test_reset_logs_out_other_devices(capsys):
    laptop = signup("devices@example.com")
    new_client().post("/api/auth/forgot-password", json={"email": "devices@example.com"})
    new_client().post("/api/auth/reset-password", json={"token": reset_link_token(capsys), "new_password": "a brand new password"})
    assert laptop.get("/api/auth/me").status_code == 401


def test_expired_or_fake_reset_links_fail():
    r = new_client().post("/api/auth/reset-password", json={"token": "x" * 43, "new_password": "a brand new password"})
    assert r.status_code == 400


def test_shared_wifi_is_not_locked_out_by_one_persons_typos():
    signup("classmate@example.com")
    typo_person = new_client()
    for _ in range(5):  # one person locks only their own email...
        typo_person.post("/api/auth/login", json={"email": "typo@example.com", "password": "wrong password!!"})
    # ...someone else on the same network can still log in.
    r = new_client().post("/api/auth/login", json={"email": "classmate@example.com", "password": PASSWORD})
    assert r.status_code == 200


def test_signing_up_twice_does_not_block_logging_in():
    signup("twice@example.com")
    client = new_client()
    for _ in range(6):
        client.post("/api/auth/signup", json={"email": "twice@example.com", "password": PASSWORD})
    assert client.post("/api/auth/login", json={"email": "twice@example.com", "password": PASSWORD}).status_code == 200


def test_live_site_says_so_when_email_is_not_set_up(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    r = new_client().post("/api/auth/forgot-password", json={"email": "anyone@example.com"})
    assert r.status_code == 503 and "aren't set up" in r.json()["detail"]
