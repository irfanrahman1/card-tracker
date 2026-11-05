"""Endpoints for purchases. Every route is for the logged-in user only."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import current_user
from ..database import get_db
from ..ingest import save_from_source
from ..sources import CSVSource, ManualSource
from .cards import get_own_card
from .insights import card_filter

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def get_own_transaction(db: Session, user: models.User, transaction_id: int) -> models.Transaction:
    """A purchase by id, but only if it's this user's (otherwise 404, as if it didn't exist)."""
    row = db.get(models.Transaction, transaction_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Transaction not found")
    return row


@router.get("", response_model=list[schemas.TransactionOut])
def list_transactions(
    month: str | None = None, category: str | None = None, card: str | None = None,
    db: Session = Depends(get_db), user: models.User = Depends(current_user),
):
    """List your purchases, newest first. Optional filters: `month` like '2026-10',
    `category`, and `card` (a card id, or "none" for purchases with no card)."""
    query = select(models.Transaction).where(models.Transaction.user_id == user.id).order_by(
        models.Transaction.date.desc(), models.Transaction.id.desc()
    )
    if category:
        query = query.where(models.Transaction.category == category)
    rows = card_filter(db.scalars(query).all(), card)
    if month:
        rows = [t for t in rows if t.date.strftime("%Y-%m") == month]
    return rows


@router.post("", response_model=schemas.TransactionOut, status_code=201)
def add_transaction(payload: schemas.TransactionIn, db: Session = Depends(get_db),
                    user: models.User = Depends(current_user)):
    """Add one purchase by hand."""
    if payload.amount <= 0:
        raise HTTPException(400, "Amount must be more than zero")
    if payload.card_id is not None:
        get_own_card(db, user, payload.card_id)
    return save_from_source(db, ManualSource([payload]), user)[0]


@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    card_id: int | None = Form(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    """Import purchases from a CSV file.

    `card_id` (optional) is used for rows that don't name a card themselves.
    Returns how many rows were imported and which were skipped and why.
    """
    content = await file.read()
    if len(content) > 5_000_000:
        raise HTTPException(400, "File too large (max 5 MB)")
    if card_id is not None:
        get_own_card(db, user, card_id)
    cards = db.scalars(select(models.Card).where(models.Card.user_id == user.id)).all()
    source = CSVSource(content, {c.name: c.id for c in cards}, default_card_id=card_id)
    try:
        created = save_from_source(db, source, user)
    except ValueError as err:
        raise HTTPException(400, str(err))
    return {"imported": len(created), "skipped": source.skipped}


@router.post("/assign-card")
def assign_card(payload: schemas.AssignCardIn, db: Session = Depends(get_db),
                user: models.User = Depends(current_user)):
    """Link your purchases to a card in one go (by default only ones with no card yet).

    Saves re-uploading a CSV just because the card wasn't picked the first time.
    """
    get_own_card(db, user, payload.card_id)
    query = select(models.Transaction).where(models.Transaction.user_id == user.id)
    if payload.only_without_card:
        query = query.where(models.Transaction.card_id.is_(None))
    rows = db.scalars(query).all()
    for row in rows:
        row.card_id = payload.card_id
    db.commit()
    return {"updated": len(rows)}


@router.patch("/{transaction_id}")
def update_transaction(transaction_id: int, payload: schemas.TransactionUpdate, db: Session = Depends(get_db),
                       user: models.User = Depends(current_user)):
    """Change a purchase's category and/or card.

    Changing the category (with apply_to_merchant, the default) also re-categorizes
    your other purchases from the same merchant and remembers the choice for future imports.
    Returns how many purchases changed.
    """
    row = get_own_transaction(db, user, transaction_id)
    if "card_id" in payload.model_fields_set:
        if payload.card_id is not None:
            get_own_card(db, user, payload.card_id)
        row.card_id = payload.card_id

    updated = 1
    if payload.category:
        row.category = payload.category
        if payload.apply_to_merchant:
            same = db.scalars(select(models.Transaction).where(
                models.Transaction.user_id == user.id,
                func.lower(models.Transaction.merchant) == row.merchant.lower(),
                models.Transaction.id != row.id,
            )).all()
            for other in same:
                other.category = payload.category
            updated += len(same)
            # Remember it: your future imports of this merchant get this category.
            key = row.merchant.lower()
            rule = db.scalar(select(models.MerchantRule).where(
                models.MerchantRule.user_id == user.id, models.MerchantRule.merchant == key))
            if rule:
                rule.category = payload.category
            else:
                db.add(models.MerchantRule(user_id=user.id, merchant=key, category=payload.category))
    db.commit()
    return {"updated": updated, "merchant": row.merchant, "category": row.category}


@router.delete("/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db),
                       user: models.User = Depends(current_user)):
    row = get_own_transaction(db, user, transaction_id)
    db.delete(row)
    db.commit()
