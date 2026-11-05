"""Endpoints for purchases."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..ingest import save_from_source
from .insights import card_filter
from ..sources import CSVSource, ManualSource

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=list[schemas.TransactionOut])
def list_transactions(
    month: str | None = None, category: str | None = None, card: str | None = None,
    db: Session = Depends(get_db),
):
    """List purchases, newest first. Optional filters: `month` like '2026-10', `category`,
    and `card` (a card id, or "none" for purchases with no card)."""
    query = select(models.Transaction).order_by(
        models.Transaction.date.desc(), models.Transaction.id.desc()
    )
    if category:
        query = query.where(models.Transaction.category == category)
    rows = card_filter(db.scalars(query).all(), card)
    if month:
        rows = [t for t in rows if t.date.strftime("%Y-%m") == month]
    return rows


@router.post("", response_model=schemas.TransactionOut, status_code=201)
def add_transaction(payload: schemas.TransactionIn, db: Session = Depends(get_db)):
    """Add one purchase by hand."""
    if payload.amount <= 0:
        raise HTTPException(400, "Amount must be more than zero")
    if payload.card_id is not None and not db.get(models.Card, payload.card_id):
        raise HTTPException(400, "Unknown card_id")
    return save_from_source(db, ManualSource([payload]))[0]


@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    card_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """Import purchases from a CSV file.

    `card_id` (optional) is used for rows that don't name a card themselves.
    Returns how many rows were imported and which were skipped and why.
    """
    content = await file.read()
    if len(content) > 5_000_000:
        raise HTTPException(400, "File too large (max 5 MB)")
    cards = db.scalars(select(models.Card)).all()
    source = CSVSource(content, {c.name: c.id for c in cards}, default_card_id=card_id)
    try:
        created = save_from_source(db, source)
    except ValueError as err:
        raise HTTPException(400, str(err))
    return {"imported": len(created), "skipped": source.skipped}


@router.post("/assign-card")
def assign_card(payload: schemas.AssignCardIn, db: Session = Depends(get_db)):
    """Link purchases to a card in one go (by default only ones with no card yet).

    Saves re-uploading a CSV just because the card wasn't picked the first time.
    """
    if not db.get(models.Card, payload.card_id):
        raise HTTPException(400, "Unknown card_id")
    query = select(models.Transaction)
    if payload.only_without_card:
        query = query.where(models.Transaction.card_id.is_(None))
    rows = db.scalars(query).all()
    for row in rows:
        row.card_id = payload.card_id
    db.commit()
    return {"updated": len(rows)}


@router.patch("/{transaction_id}")
def update_transaction(transaction_id: int, payload: schemas.TransactionUpdate, db: Session = Depends(get_db)):
    """Change a purchase's category and/or card.

    Changing the category (with apply_to_merchant, the default) also re-categorizes
    every purchase from the same merchant and remembers the choice for future imports.
    Returns how many purchases changed.
    """
    row = db.get(models.Transaction, transaction_id)
    if not row:
        raise HTTPException(404, "Transaction not found")
    fields = payload.model_fields_set
    if "card_id" in fields:
        if payload.card_id is not None and not db.get(models.Card, payload.card_id):
            raise HTTPException(400, "Unknown card_id")
        row.card_id = payload.card_id

    updated = 1
    if payload.category:
        row.category = payload.category
        if payload.apply_to_merchant:
            same = db.scalars(select(models.Transaction).where(
                func.lower(models.Transaction.merchant) == row.merchant.lower(),
                models.Transaction.id != row.id,
            )).all()
            for other in same:
                other.category = payload.category
            updated += len(same)
            # Remember it: future imports of this merchant get this category.
            key = row.merchant.lower()
            rule = db.scalar(select(models.MerchantRule).where(models.MerchantRule.merchant == key))
            if rule:
                rule.category = payload.category
            else:
                db.add(models.MerchantRule(merchant=key, category=payload.category))
    db.commit()
    return {"updated": updated, "merchant": row.merchant, "category": row.category}


@router.delete("/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    row = db.get(models.Transaction, transaction_id)
    if not row:
        raise HTTPException(404, "Transaction not found")
    db.delete(row)
    db.commit()
