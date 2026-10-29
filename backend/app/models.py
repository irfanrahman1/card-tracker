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
    # Rewards are stored as a percent back (3.0 = 3% / 3x points per dollar).
    base_rate: Mapped[float] = mapped_column(Float, default=1.0)

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
