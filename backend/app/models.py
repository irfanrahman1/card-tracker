"""Database tables.

Every card, purchase and category rule belongs to one user (user_id), and every
query filters by the logged-in user, so people never see each other's data.
"""
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    """An account. Only an email is stored, never the password itself."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lowercase
    # Argon2 hash of the password (a one-way scramble that can't be reversed).
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # Demo accounts are throwaway sample accounts, deleted after a day.
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class FailedAttempt(Base):
    """A failed login (or a demo/sign-up attempt), for brute-force limits. Stored in the
    database so the limit holds across servers and restarts. The key is a hash of
    "ip:..." or "email:...", so no raw addresses or emails are kept here."""

    __tablename__ = "failed_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), index=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class PasswordReset(Base):
    """A one-time "forgot password" link. Only a hash of the token is stored; it expires
    after 30 minutes and can be used once."""

    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class LoginSession(Base):
    """A logged-in browser. The cookie holds a random token; only its SHA-256 hash is
    stored, so a leaked database can't be used to log in as anyone."""

    __tablename__ = "login_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Card(Base):
    """A credit card. `base_rate` applies to any category without its own rule."""

    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Owner. (Nullable only so older databases can be upgraded; see auth.claim_legacy_data.)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(100))
    issuer: Mapped[str] = mapped_column(String(100), default="")
    # Rates are "per dollar": 3.0 = 3% cash back, or 3 points per dollar.
    base_rate: Mapped[float] = mapped_column(Float, default=1.0)
    # "cash" (rate is a %) or "points" (rate is points per dollar).
    reward_type: Mapped[str] = mapped_column(String(10), default="cash")
    # What one point is worth to you, in cents. Cash back is always 1.0.
    point_value: Mapped[float] = mapped_column(Float, default=1.0)
    annual_fee: Mapped[float] = mapped_column(Float, default=0.0)
    # Yearly value of perks/credits you actually use (e.g. $200 airline credit), in dollars.
    credits_value: Mapped[float] = mapped_column(Float, default=0.0)
    # Which catalog card this was created from, if any (see catalog/cards.json).
    catalog_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    rules: Mapped[list["RewardRule"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )


class RewardRule(Base):
    """A bonus rate for one category on one card, e.g. 'groceries at 4%'."""

    __tablename__ = "reward_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(30))
    rate: Mapped[float] = mapped_column(Float)
    # Yearly spend limit for this rate in dollars (then the base rate applies). None = no cap.
    cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Rules with the same cap_group on a card share one cap (e.g. BofA's $2,500/quarter
    # across your 3% choice and 2% groceries). None = the cap is this rule's own.
    cap_group: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Share of a year's spending this rate can apply to. 0.25 = one quarter, for
    # rotating 5% categories like Discover's. 1.0 = all year.
    portion: Mapped[float] = mapped_column(Float, default=1.0)
    # Last day the rate applies, as "YYYY-MM-DD" (rotating categories end each quarter).
    valid_until: Mapped[str | None] = mapped_column(String(10), nullable=True)

    card: Mapped[Card] = relationship(back_populates="rules")


class Transaction(Base):
    """A single purchase, no matter where it came from."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    date: Mapped[date] = mapped_column(Date)
    merchant: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(300), default="")
    # Positive = purchase, negative = refund or statement credit (subtracts from its category).
    amount: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(30))
    # Which card paid. Optional: CSV rows or manual entries may not say.
    card_id: Mapped[int | None] = mapped_column(
        ForeignKey("cards.id", ondelete="SET NULL"), nullable=True
    )
    # Where the row came from: "manual", "csv", "demo", later "plaid".
    source: Mapped[str] = mapped_column(String(20), default="manual")
    # The source's own id for this row (e.g. Plaid transaction_id), used to skip duplicates.
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Which upload (CSV or PDF) this purchase came from, so a whole upload can be undone.
    # Empty for purchases typed in by hand, demo data, and uploads from before this existed.
    import_id: Mapped[int | None] = mapped_column(
        ForeignKey("imports.id", ondelete="SET NULL"), nullable=True, index=True
    )


class Import(Base):
    """One uploaded file (CSV or PDF statement). Lets you undo a whole upload in one click."""

    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(20))  # "csv" or "pdf"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    count: Mapped[int] = mapped_column(Integer, default=0)  # purchases saved by this upload


class MerchantRule(Base):
    """A category the user chose for a merchant; applied to future imports of that merchant."""

    # New table name: the old "merchant_rules" table had one global rule per merchant,
    # but each user needs their own. Old rules are copied over (see auth.claim_legacy_data).
    __tablename__ = "category_rules"
    __table_args__ = (UniqueConstraint("user_id", "merchant"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    merchant: Mapped[str] = mapped_column(String(200))  # lowercased merchant name
    category: Mapped[str] = mapped_column(String(30))
