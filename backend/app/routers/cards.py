"""Endpoints for credit cards and their reward rules."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/cards", tags=["cards"])


def _rules_from(payload: schemas.CardIn) -> list[models.RewardRule]:
    # If the same category is listed twice, the last one wins.
    by_category = {rule.category: rule.rate for rule in payload.rules}
    return [models.RewardRule(category=c, rate=r) for c, r in by_category.items()]


@router.get("", response_model=list[schemas.CardOut])
def list_cards(db: Session = Depends(get_db)):
    return db.scalars(select(models.Card).order_by(models.Card.name)).all()


@router.post("", response_model=schemas.CardOut, status_code=201)
def create_card(payload: schemas.CardIn, db: Session = Depends(get_db)):
    card = models.Card(
        name=payload.name, issuer=payload.issuer, base_rate=payload.base_rate,
        rules=_rules_from(payload),
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.put("/{card_id}", response_model=schemas.CardOut)
def update_card(card_id: int, payload: schemas.CardIn, db: Session = Depends(get_db)):
    card = db.get(models.Card, card_id)
    if not card:
        raise HTTPException(404, "Card not found")
    card.name = payload.name
    card.issuer = payload.issuer
    card.base_rate = payload.base_rate
    card.rules = _rules_from(payload)  # replace all rules with the submitted set
    db.commit()
    db.refresh(card)
    return card


@router.delete("/{card_id}", status_code=204)
def delete_card(card_id: int, db: Session = Depends(get_db)):
    card = db.get(models.Card, card_id)
    if not card:
        raise HTTPException(404, "Card not found")
    db.delete(card)
    db.commit()
