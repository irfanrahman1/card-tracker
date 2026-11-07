"""Endpoints for purchases. Every route is for the logged-in user only."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import current_user
from ..database import get_db
from ..categories import clean_merchant
from ..ingest import pick_category, save_from_source
from ..sources import CSVSource, ManualSource, PDFSource
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


async def read_pdf(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > 5_000_000:
        raise HTTPException(400, "File too large (max 5 MB)")
    if not content.startswith(b"%PDF"):
        raise HTTPException(400, "That file isn't a PDF.")
    return content


@router.post("/upload-pdf/preview")
async def preview_pdf(
    file: UploadFile = File(...),
    card_id: int | None = Form(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    """Read a PDF statement and show what would be imported. Nothing is saved yet:
    the review screen shows this, then calls /upload-pdf to actually import."""
    content = await read_pdf(file)
    if card_id is not None:
        get_own_card(db, user, card_id)
    source = PDFSource(content, default_card_id=card_id)
    try:
        items = source.fetch()
    except ValueError as err:
        raise HTTPException(400, str(err))

    # so the review screen can show which rows you've imported before, and the
    # category each one will get (including categories you've fixed by hand before)
    already = set(db.scalars(select(models.Transaction.external_id).where(
        models.Transaction.user_id == user.id, models.Transaction.source == "pdf")))
    rules = {r.merchant: r.category for r in db.scalars(
        select(models.MerchantRule).where(models.MerchantRule.user_id == user.id))}

    rows = []
    for item in items:
        merchant = clean_merchant(item.merchant)
        rows.append({
            "id": item.external_id,
            "date": item.date,
            "merchant": merchant,
            "amount": item.amount,
            "category": pick_category(item, merchant, rules, "pdf"),
            "already_imported": item.external_id in already,
        })
    return {
        "parser": source.parser_name,
        "rows": rows,
        "skipped": source.skipped,
        "warnings": source.warnings,
        "totals_checked": source.totals_checked,
    }


@router.post("/upload-pdf")
async def import_pdf(
    file: UploadFile = File(...),
    card_id: int | None = Form(None),
    leave_out: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    """Import a PDF statement after the review screen.
    `leave_out`: comma-separated ids of rows you unticked."""
    content = await read_pdf(file)
    if card_id is not None:
        get_own_card(db, user, card_id)
    unticked = {i for i in leave_out.split(",") if i}
    source = PDFSource(content, default_card_id=card_id, leave_out=unticked)
    try:
        created = save_from_source(db, source, user)
    except ValueError as err:
        raise HTTPException(400, str(err))
    return {"imported": len(created), "skipped": source.skipped, "warnings": source.warnings}


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
