"""Monthly spending summary and the best-card recommendation."""
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..categories import CATEGORIES, normalize_category
from ..database import get_db
from ..catalog import catalog_cards
from ..optimizer import suggest
from ..recommendation import best_card, point_value, rank_cards, rate_for

router = APIRouter(prefix="/api", tags=["insights"])


@router.get("/summary")
def monthly_summary(month: str | None = None, db: Session = Depends(get_db)):
    """Spending by category for one month ('YYYY-MM').

    Defaults to the most recent month that has purchases. Also reports, for purchases
    made with a known card, the rewards earned vs. what the best card would have earned.
    """
    transactions = db.scalars(select(models.Transaction)).all()
    cards = db.scalars(select(models.Card)).all()
    cards_by_id = {c.id: c for c in cards}

    months = sorted({t.date.strftime("%Y-%m") for t in transactions}, reverse=True)
    if month is None:
        month = months[0] if months else date.today().strftime("%Y-%m")

    # Every category shows, even at $0. Refunds (negative amounts) subtract from theirs.
    by_category = {c: 0.0 for c in CATEGORIES}
    earned = possible = refunds = 0.0
    count = with_card = 0
    for t in transactions:
        if t.date.strftime("%Y-%m") != month:
            continue
        if t.amount > 0:
            count += 1
        else:
            refunds += -t.amount
        by_category[t.category] = by_category.get(t.category, 0) + t.amount
        # Compare only purchases made with a known card, so the two numbers match up.
        # Card fees don't earn rewards, so they're left out.
        if t.card_id in cards_by_id and t.category != "fees":
            with_card += 1
            card = cards_by_id[t.card_id]
            rate, _ = rate_for(card, t.category)
            cents = rate * point_value(card)  # value per dollar, so points count fairly
            earned += t.amount * cents / 100
            # A refund takes back what its own card earned, whatever the "best" card is.
            best_cents = best_card(cards, t.category, t.amount).cents_per_dollar if t.amount > 0 else cents
            possible += t.amount * best_cents / 100

    return {
        "month": month,
        "months": months,  # all months with data, newest first (for a picker)
        "total": round(sum(by_category.values()), 2),
        "count": count,  # purchases (refunds not counted)
        "refunds": round(refunds, 2),  # total refunds/credits this month
        "with_card": with_card,  # purchases linked to one of your cards
        "by_category": {c: round(v, 2) for c, v in by_category.items()},
        "rewards_earned": round(earned, 2),
        "rewards_possible": round(possible, 2),
    }


@router.get("/summary/trend")
def monthly_trend(db: Session = Depends(get_db)):
    """Spending by category for every month, oldest first (for a chart)."""
    totals = defaultdict(lambda: {c: 0.0 for c in CATEGORIES})
    for t in db.scalars(select(models.Transaction)):
        totals[t.date.strftime("%Y-%m")][t.category] += t.amount
    return [
        {"month": m, **{c: round(v, 2) for c, v in totals[m].items()}}
        for m in sorted(totals)
    ]


@router.get("/recommend")
def recommend(
    amount: float = Query(gt=0),
    category: str | None = None,
    merchant: str = "",
    db: Session = Depends(get_db),
):
    """Best card for a purchase. Give a category, or a merchant to guess it from."""
    if not category and not merchant:
        raise HTTPException(400, "Provide a category or a merchant")
    resolved = normalize_category(category, merchant)
    cards = db.scalars(select(models.Card)).all()
    ranked = rank_cards(cards, resolved, amount)
    return {
        "category": resolved,
        "amount": amount,
        "best": ranked[0] if ranked else None,
        "options": ranked,
    }


# ---------- Wallet optimizer ----------

def yearly_spending(db: Session) -> tuple[dict[str, float], int]:
    """Your spending per category over the last 12 months with data, scaled to a year.

    Returns (spending, months_of_data). With 3 months of data, totals are x4.
    Refunds are netted in; a category that nets negative counts as $0.
    """
    rows = db.scalars(select(models.Transaction)).all()
    months = sorted({t.date.strftime("%Y-%m") for t in rows}, reverse=True)[:12]
    if not months:
        return {c: 0.0 for c in CATEGORIES}, 0
    totals = {c: 0.0 for c in CATEGORIES}
    for t in rows:
        if t.date.strftime("%Y-%m") in months:
            totals[t.category] = totals.get(t.category, 0) + t.amount
    scale = 12 / len(months)
    return {c: round(max(v, 0) * scale, 2) for c, v in totals.items()}, len(months)


def _owned_as_dicts(cards) -> list[dict]:
    return [{
        "key": card.catalog_id or f"own-{card.id}",
        "id": card.id,
        "name": card.name,
        "base_rate": card.base_rate,
        "point_value": point_value(card),
        "annual_fee": card.annual_fee or 0.0,
        "credits_value": card.credits_value or 0.0,
        "rules": [{"category": r.category, "rate": r.rate, "cap": r.cap} for r in card.rules],
        "owned": True,
    } for card in cards]


def _catalog_as_dicts(points_cents: float) -> list[dict]:
    return [{
        "key": spec["id"],
        "name": f"{spec['issuer']} {spec['name']}",
        "base_rate": spec["base_rate"],
        "point_value": 1.0 if spec["reward_type"] == "cash" else points_cents,
        "annual_fee": spec["annual_fee"],
        "credits_value": 0.0,  # unknown: depends on which perks you'd use
        "rules": spec["rules"],
        "notes": spec.get("notes", ""),
        "owned": False,
    } for spec in catalog_cards()]


@router.post("/optimizer")
def optimize(payload: schemas.OptimizerIn | None = None, db: Session = Depends(get_db)):
    """Yearly value of your cards, and which cards would add the most.

    Uses your real spending (last 12 months, scaled to a year) unless you pass
    `spending` to try a what-if. Catalog points cards are valued at `point_value` cents.
    """
    payload = payload or schemas.OptimizerIn()
    real_spending, months = yearly_spending(db)
    spending = {c: max(float(payload.spending.get(c, 0)), 0) for c in CATEGORIES} if payload.spending else real_spending
    owned = _owned_as_dicts(db.scalars(select(models.Card)).all())
    result = suggest(owned, _catalog_as_dicts(payload.point_value), spending)
    return {"spending": spending, "months_of_data": months, "what_if": bool(payload.spending), **result}
