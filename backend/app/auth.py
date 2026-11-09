"""Accounts, passwords and login sessions.

How it keeps people safe:
  - Passwords are hashed with Argon2 (slow on purpose, salted). The password itself
    is never stored or logged.
  - Logging in creates a random 256-bit token sent as a cookie the browser's
    JavaScript can't read (HttpOnly) and that's never sent to other sites
    (SameSite=Lax). Only a SHA-256 hash of the token is stored.
  - Every data route depends on current_user(), and every query filters by that
    user's id, so one account can never read another's cards or purchases.
  - Repeated failed logins from the same address or for the same email are blocked
    for a while (brute-force protection), tracked in the database.
"""
import hashlib
import os
import re
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import func, inspect, select, text, update
from sqlalchemy.orm import Session

from . import models
from .database import engine, get_db

COOKIE_NAME = "ct_session"
SESSION_DAYS = 30
DEMO_HOURS = 24
# Set COOKIE_SECURE=true in production (HTTPS) so the cookie is never sent over plain HTTP.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

_hasher = PasswordHasher()  # Argon2id with the library's recommended settings
# Used to spend the same time when an email doesn't exist, so response time
# doesn't reveal which emails have accounts.
_DUMMY_HASH = _hasher.hash("not-a-real-password")

def utcnow() -> datetime:
    """Current UTC time without a timezone attached (how the database stores it)."""
    return datetime.now(UTC).replace(tzinfo=None)


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- Passwords ----------

def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def check_new_password(password: str, email: str) -> None:
    """Basic rules for a new password. Length matters most."""
    if len(password) < 10:
        raise HTTPException(400, "Use at least 10 characters for your password")
    if len(password) > 128:
        raise HTTPException(400, "Password is too long (128 characters max)")
    if password.lower() in {email.lower(), email.split("@")[0].lower()}:
        raise HTTPException(400, "Don't use your email as your password")


def normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise HTTPException(400, "Enter a valid email address")
    return email


# ---------- Brute-force protection ----------

class LoginLimiter:
    """Blocks an IP address or email after too many failed logins in a time window.

    Failures are kept in the database (hashed), so the limit works even when the app
    runs as many short-lived copies (serverless) or restarts.
    """

    # How many failures each kind of key allows per window. Per email stays strict (it's
    # what protects one account from password guessing); per network is looser, because
    # many people can share one address (a college or office Wi-Fi).
    LIMITS = {"email": 5, "ip": 20, "signup-ip": 20, "reset-email": 5, "reset-ip": 20, "demo": 10}

    def __init__(self, window_seconds: int = 15 * 60):
        self.window = timedelta(seconds=window_seconds)

    def limit_for(self, key: str) -> int:
        return self.LIMITS.get(key.split(":", 1)[0], 5)

    @staticmethod
    def _hash(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    def check(self, db: Session, *keys: str) -> None:
        since = utcnow() - self.window
        for key in keys:
            count = db.scalar(select(func.count()).select_from(models.FailedAttempt).where(
                models.FailedAttempt.key_hash == self._hash(key), models.FailedAttempt.at > since))
            if count >= self.limit_for(key):
                raise HTTPException(429, "Too many attempts. Wait 15 minutes and try again. "
                                         "Forgot your password? Use \"Forgot password?\" on the Log in tab.")

    def failed(self, db: Session, *keys: str) -> None:
        for key in keys:
            db.add(models.FailedAttempt(key_hash=self._hash(key)))
        db.commit()

    def succeeded(self, db: Session, *keys: str) -> None:
        hashes = [self._hash(k) for k in keys]
        db.query(models.FailedAttempt).filter(models.FailedAttempt.key_hash.in_(hashes)).delete(synchronize_session=False)
        db.commit()


limiter = LoginLimiter()


# How many proxies sit in front of the app (set TRUSTED_PROXY_HOPS=1 on Cloud Run and
# similar hosts). Each proxy adds the address it saw to the end of X-Forwarded-For;
# anything before that was typed by the visitor and can be faked, so it's ignored.
TRUSTED_PROXY_HOPS = int(os.environ.get("TRUSTED_PROXY_HOPS", "0"))


def client_ip(request: Request) -> str:
    """The visitor's address, used for brute-force limits."""
    if TRUSTED_PROXY_HOPS:
        hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
        if len(hops) >= TRUSTED_PROXY_HOPS:
            return hops[-TRUSTED_PROXY_HOPS]
    return request.client.host if request.client else "unknown"


# ---------- Sessions ----------

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(db: Session, response: Response, user: models.User) -> None:
    """Log a user in: store a hashed random token and send the token as a cookie."""
    token = secrets.token_urlsafe(32)
    lifetime = timedelta(hours=DEMO_HOURS) if user.is_demo else timedelta(days=SESSION_DAYS)
    db.add(models.LoginSession(user_id=user.id, token_hash=_hash_token(token),
                               expires_at=utcnow() + lifetime))
    db.commit()
    response.set_cookie(
        COOKIE_NAME, token, max_age=int(lifetime.total_seconds()),
        httponly=True, secure=COOKIE_SECURE, samesite="lax", path="/",
    )


def end_session(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.query(models.LoginSession).filter_by(token_hash=_hash_token(token)).delete()
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


def current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    """FastAPI dependency: the logged-in user, or a 401 error."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        session = db.scalar(select(models.LoginSession).where(
            models.LoginSession.token_hash == _hash_token(token)))
        if session and session.expires_at > utcnow():
            user = db.get(models.User, session.user_id)
            if user:
                return user
    raise HTTPException(401, "Please log in")


# ---------- Housekeeping ----------

def delete_expired(db: Session) -> None:
    """Remove expired sessions and demo accounts older than a day (with all their data)."""
    now = utcnow()
    db.query(models.LoginSession).filter(models.LoginSession.expires_at < now).delete()
    db.query(models.FailedAttempt).filter(models.FailedAttempt.at < now - timedelta(days=1)).delete()
    db.query(models.PasswordReset).filter(models.PasswordReset.expires_at < now).delete()
    old_demos = db.scalars(select(models.User).where(
        models.User.is_demo.is_(True), models.User.created_at < now - timedelta(hours=DEMO_HOURS))).all()
    for user in old_demos:
        delete_user_data(db, user.id)
        db.delete(user)
    db.commit()


def delete_user_data(db: Session, user_id: int, sessions: bool = True) -> None:
    """Delete every card, purchase and category rule a user has (and, by default,
    their login sessions too)."""
    card_ids = select(models.Card.id).where(models.Card.user_id == user_id)
    db.query(models.RewardRule).filter(models.RewardRule.card_id.in_(card_ids)).delete(synchronize_session=False)
    # purchases before imports: purchases point to the upload they came from
    tables = [models.Transaction, models.Import, models.Card, models.MerchantRule] + (
        [models.LoginSession, models.PasswordReset] if sessions else [])
    for model in tables:
        db.query(model).filter(model.user_id == user_id).delete(synchronize_session=False)


def claim_legacy_data(db: Session, user: models.User) -> None:
    """Data from before accounts existed (user_id empty) goes to the first real account.

    This is how your existing cards and purchases on your own computer carry over
    when you sign up. On a fresh hosted database there's nothing to claim.
    """
    for model in (models.Card, models.Transaction, models.MerchantRule):
        db.execute(update(model).where(model.user_id.is_(None)).values(user_id=user.id))
    # Category fixes from the old one-rule-per-merchant table.
    if inspect(engine).has_table("merchant_rules"):
        old = db.execute(text("SELECT merchant, category FROM merchant_rules")).all()
        have = set(db.scalars(select(models.MerchantRule.merchant).where(models.MerchantRule.user_id == user.id)))
        for merchant, category in old:
            if merchant not in have:
                db.add(models.MerchantRule(user_id=user.id, merchant=merchant, category=category))
        db.execute(text("DELETE FROM merchant_rules"))
    db.commit()
