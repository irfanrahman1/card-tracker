"""Monthly spending summary and the best-card recommendation."""
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..categories import CATEGORIES, normalize_category
from ..database import get_db
from ..recommendation import best_card, rank_cards, rate_for

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
            rate, _ = rate_for(cards_by_id[t.card_id], t.category)
            earned += t.amount * rate / 100
            # A refund takes back what its own card earned, whatever the "best" card is.
            best_rate = best_card(cards, t.category, t.amount).rate if t.amount > 0 else rate
            possible += t.amount * best_rate / 100

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
