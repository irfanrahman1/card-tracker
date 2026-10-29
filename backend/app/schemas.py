"""Request/response shapes for the API (validated by Pydantic)."""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .categories import CATEGORIES


class RewardRuleIn(BaseModel):
    category: str
    rate: float = Field(ge=0)

    @field_validator("category")
    @classmethod
    def known_category(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}")
        return value


class RewardRuleOut(RewardRuleIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class CardIn(BaseModel):
    name: str = Field(min_length=1)
    issuer: str = ""
    base_rate: float = Field(default=1.0, ge=0)
    rules: list[RewardRuleIn] = []


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    issuer: str
    base_rate: float
    rules: list[RewardRuleOut]


class TransactionIn(BaseModel):
    """A purchase as handed to us by any source (manual form, CSV, Plaid...).

    `category` is optional; it gets normalized/guessed before saving.
    """

    date: date
    merchant: str = Field(min_length=1)
    description: str = ""
    # Positive = purchase, negative = refund/credit. Zero isn't allowed.
    amount: float
    category: str | None = None
    card_id: int | None = None
    external_id: str | None = None

    @field_validator("amount")
    @classmethod
    def not_zero(cls, value: float) -> float:
        if value == 0:
            raise ValueError("amount can't be zero")
        return value


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: date
    merchant: str
    description: str
    amount: float
    category: str
    card_id: int | None
    source: str


class TransactionUpdate(BaseModel):
    """Fields you can change on a purchase after it's saved."""

    category: str | None = None
    card_id: int | None = None
    # When changing the category: also update this merchant's other purchases and
    # remember the choice for future imports.
    apply_to_merchant: bool = True

    @field_validator("category")
    @classmethod
    def known_category(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().lower()
        if value not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}")
        return value
