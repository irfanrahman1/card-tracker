"""Database tables."""
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Card(Base):
    """A credit card. `base_rate` applies to any category without its own rule."""

    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
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


class MerchantRule(Base):
    """A category the user chose for a merchant; applied to future imports of that merchant."""

    __tablename__ = "merchant_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant: Mapped[str] = mapped_column(String(200), unique=True)  # lowercased merchant name
    category: Mapped[str] = mapped_column(String(30))
