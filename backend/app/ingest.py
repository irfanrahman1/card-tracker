"""Save transactions from any TransactionSource into the database.

This is the single place where incoming purchases are cleaned up, so every
source (manual, CSV, demo, Plaid) gets the same treatment.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .categories import clean_merchant, is_amazon, normalize_category
from .sources.base import TransactionSource


def pick_category(item, merchant: str, rules: dict[str, str], source_name: str) -> str:
    """Choose a category: Amazon rule > your saved merchant rule > the usual guessing.

    A category typed in by hand (manual source) beats a saved rule.
    """
    if is_amazon(merchant):
        return "shopping"
    typed_by_hand = source_name == "manual" and item.category
    rule = rules.get(merchant.lower())
    if rule and not typed_by_hand:
        return rule
    # Guess from the raw name: prefixes like "TST*" (a restaurant terminal) are clues.
    return normalize_category(item.category, item.merchant, item.description)


def save_from_source(db: Session, source: TransactionSource, user: models.User) -> list[models.Transaction]:
    """Fetch from `source`, normalize each row, skip duplicates, and save for `user`.

    Returns the newly created rows.
    """
    known_card_ids = set(db.scalars(select(models.Card.id).where(models.Card.user_id == user.id)))
    rules = {r.merchant: r.category for r in db.scalars(
        select(models.MerchantRule).where(models.MerchantRule.user_id == user.id))}
    created = []

    for item in source.fetch():
        # Skip rows we've already imported from this source (matters for Plaid
        # syncs and re-uploaded CSVs).
        if item.external_id:
            exists = db.scalar(
                select(models.Transaction.id).where(
                    models.Transaction.user_id == user.id,
                    models.Transaction.source == source.name,
                    models.Transaction.external_id == item.external_id,
                )
            )
            if exists:
                continue

        merchant = clean_merchant(item.merchant)
        row = models.Transaction(
            user_id=user.id,
            date=item.date,
            merchant=merchant,
            description=item.description.strip(),
            amount=round(item.amount, 2),
            category=pick_category(item, merchant, rules, source.name),
            # Ignore card ids that don't exist (or aren't yours) rather than failing the import.
            card_id=item.card_id if item.card_id in known_card_ids else None,
            source=source.name,
            external_id=item.external_id,
        )
        db.add(row)
        created.append(row)

    db.commit()
    for row in created:
        db.refresh(row)
    return created
