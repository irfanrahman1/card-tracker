"""Endpoints for credit cards and their reward rules. Every route is for the logged-in user only."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import current_user
from ..catalog import catalog_cards, display_name, find_card
from ..database import get_db
from ..recommendation import point_value, rate_for

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


def card_from_catalog(spec: dict, user: models.User, choice: str | None = None) -> models.Card:
    """A new (unsaved) card for `user` built from a catalog entry.

    Cards where you pick a bonus category (e.g. BofA Customized Cash) take `choice`.
    """
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
    card = models.Card(user_id=user.id)
    _apply(card, payload)
    return card


def get_own_card(db: Session, user: models.User, card_id: int) -> models.Card:
    """A card by id, but only if it belongs to this user (otherwise 404, as if it didn't exist)."""
    card = db.get(models.Card, card_id)
    if not card or card.user_id != user.id:
        raise HTTPException(404, "Card not found")
    return card


@router.get("/catalog")
def list_catalog():
    """Popular cards you can add in one click (see app/catalog/cards.json). Public."""
    return catalog_cards()


@router.post("/from-catalog/{catalog_id}", response_model=schemas.CardOut, status_code=201)
def add_from_catalog(catalog_id: str, choice: str | None = None, db: Session = Depends(get_db),
                     user: models.User = Depends(current_user)):
    """Add a catalog card to your wallet with its rules, fee and point type filled in."""
    spec = find_card(catalog_id)
    if not spec:
        raise HTTPException(404, "Unknown catalog card")
    card = card_from_catalog(spec, user, choice)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.get("", response_model=list[schemas.CardOut])
def list_cards(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    return db.scalars(select(models.Card).where(models.Card.user_id == user.id).order_by(models.Card.name)).all()


@router.get("/worth")
def cards_worth(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    """Is each card worth its annual fee?

    Adds up the rewards from your purchases on each card over the last 12 months,
    plus the perks you said you use, minus the annual fee. If a card has less than
    a year of purchases, the year is estimated from the months it does have.
    """
    since = date.today() - timedelta(days=365)
    cards = db.scalars(select(models.Card).where(models.Card.user_id == user.id)).all()

    results = []
    for card in cards:
        purchases = db.scalars(select(models.Transaction).where(
            models.Transaction.user_id == user.id,
            models.Transaction.card_id == card.id,
            models.Transaction.date >= since,
        )).all()

        rewards = 0.0
        for t in purchases:
            if t.category == "fees":
                continue  # card fees don't earn rewards
            rate, _ = rate_for(card, t.category)
            rewards += t.amount * rate * point_value(card) / 100

        # how many months of purchases we have, from the first to the last one (1 to 12)
        months = 0
        if purchases:
            first = min(t.date for t in purchases)
            last = max(t.date for t in purchases)
            months = (last.year - first.year) * 12 + (last.month - first.month) + 1
            months = min(months, 12)

        yearly_rewards = rewards / months * 12 if months else 0.0
        net = yearly_rewards + card.credits_value - card.annual_fee
        results.append({
            "card_id": card.id,
            "months": months,
            "yearly_rewards": round(yearly_rewards, 2),
            "credits": card.credits_value,
            "annual_fee": card.annual_fee,
            "net": round(net, 2),
        })
    return results


@router.post("", response_model=schemas.CardOut, status_code=201)
def create_card(payload: schemas.CardIn, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    card = models.Card(user_id=user.id)
    _apply(card, payload)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.put("/{card_id}", response_model=schemas.CardOut)
def update_card(card_id: int, payload: schemas.CardIn, db: Session = Depends(get_db),
                user: models.User = Depends(current_user)):
    card = get_own_card(db, user, card_id)
    _apply(card, payload)
    db.commit()
    db.refresh(card)
    return card


@router.delete("/{card_id}", status_code=204)
def delete_card(card_id: int, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    card = get_own_card(db, user, card_id)
    db.delete(card)
    db.commit()
