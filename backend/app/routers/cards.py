"""Endpoints for credit cards and their reward rules."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..catalog import catalog_cards, display_name, find_card
from ..database import get_db

router = APIRouter(prefix="/api/cards", tags=["cards"])


CARD_FIELDS = ["name", "issuer", "base_rate", "reward_type", "point_value", "annual_fee", "credits_value", "catalog_id"]


RULE_FIELDS = ["category", "rate", "cap", "cap_group", "portion", "valid_until"]


def _rules_from(payload: schemas.CardIn) -> list[models.RewardRule]:
    # A category can have several rules (e.g. Freedom Flex: 3% dining all year plus
    # 7% this quarter), so rules are kept as given.
    return [models.RewardRule(**{f: getattr(r, f) for f in RULE_FIELDS}) for r in payload.rules]


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
def add_from_catalog(catalog_id: str, choice: str | None = None, db: Session = Depends(get_db)):
    """Add a catalog card to your wallet with its rules, fee and point type filled in.

    Cards where you pick a bonus category (e.g. BofA Customized Cash) take `choice`.
    """
    spec = find_card(catalog_id)
    if not spec:
        raise HTTPException(404, "Unknown catalog card")
    rules = list(spec["rules"])
    if spec.get("choice"):
        pick = choice or spec["choice"]["default"]
        if pick not in spec["choice"]["options"]:
            raise HTTPException(400, f"choice must be one of {spec['choice']['options']}")
        rules.append({**{k: v for k, v in spec["choice"].items() if k not in ("options", "default", "label")}, "category": pick})
    payload = schemas.CardIn(
        name=display_name(spec),
        issuer=spec["issuer"],
        base_rate=spec["base_rate"],
        reward_type=spec["reward_type"],
        annual_fee=spec["annual_fee"],
        catalog_id=spec["id"],
        rules=[schemas.RewardRuleIn(**{f: r[f] for f in RULE_FIELDS if f in r}) for r in rules],
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
