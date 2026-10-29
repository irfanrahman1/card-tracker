"""Endpoints for credit cards and their reward rules."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..catalog import catalog_cards, find_card
from ..database import get_db

router = APIRouter(prefix="/api/cards", tags=["cards"])


CARD_FIELDS = ["name", "issuer", "base_rate", "reward_type", "point_value", "annual_fee", "credits_value", "catalog_id"]


def _rules_from(payload: schemas.CardIn) -> list[models.RewardRule]:
    # If the same category is listed twice, the last one wins.
    by_category = {rule.category: rule for rule in payload.rules}
    return [models.RewardRule(category=c, rate=r.rate, cap=r.cap) for c, r in by_category.items()]


def _apply(card: models.Card, payload: schemas.CardIn) -> None:
    for field in CARD_FIELDS:
        setattr(card, field, getattr(payload, field))
    if card.reward_type == "cash":
        card.point_value = 1.0  # cash back is worth exactly its face value
    card.rules = _rules_from(payload)  # replace all rules with the submitted set


@router.get("/catalog")
def list_catalog():
    """Popular cards you can add in one click (see app/catalog/cards.json)."""
    return catalog_cards()


@router.post("/from-catalog/{catalog_id}", response_model=schemas.CardOut, status_code=201)
def add_from_catalog(catalog_id: str, db: Session = Depends(get_db)):
    """Add a catalog card to your wallet with its rules, fee and point type filled in."""
    spec = find_card(catalog_id)
    if not spec:
        raise HTTPException(404, "Unknown catalog card")
    payload = schemas.CardIn(
        name=f"{spec['issuer']} {spec['name']}" if spec["issuer"] not in spec["name"] else spec["name"],
        issuer=spec["issuer"],
        base_rate=spec["base_rate"],
        reward_type=spec["reward_type"],
        annual_fee=spec["annual_fee"],
        catalog_id=spec["id"],
        rules=[schemas.RewardRuleIn(category=r["category"], rate=r["rate"], cap=r.get("cap")) for r in spec["rules"]],
    )
    card = models.Card()
    _apply(card, payload)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.get("", response_model=list[schemas.CardOut])
def list_cards(db: Session = Depends(get_db)):
    return db.scalars(select(models.Card).order_by(models.Card.name)).all()


@router.post("", response_model=schemas.CardOut, status_code=201)
def create_card(payload: schemas.CardIn, db: Session = Depends(get_db)):
    card = models.Card()
    _apply(card, payload)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.put("/{card_id}", response_model=schemas.CardOut)
def update_card(card_id: int, payload: schemas.CardIn, db: Session = Depends(get_db)):
    card = db.get(models.Card, card_id)
    if not card:
        raise HTTPException(404, "Card not found")
    _apply(card, payload)
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
