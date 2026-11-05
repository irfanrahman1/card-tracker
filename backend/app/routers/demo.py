"""Sample data for the logged-in user, and 'delete all my data'."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..auth import current_user, delete_user_data
from ..catalog import find_card
from ..database import get_db
from ..ingest import save_from_source
from ..sources import DEMO_CARD_IDS, DemoSource
from .cards import card_from_catalog

router = APIRouter(prefix="/api/demo", tags=["demo"])


def load_demo_data(db: Session, user: models.User) -> dict:
    """Give `user` a few popular cards and ~3 months of sample purchases.

    Safe to run more than once: cards they already have are reused, and sample
    purchases are only added once.
    """
    owned = {c.catalog_id: c for c in db.scalars(select(models.Card).where(models.Card.user_id == user.id))}
    card_ids = []
    for catalog_id in DEMO_CARD_IDS:
        card = owned.get(catalog_id)
        if not card:
            card = card_from_catalog(find_card(catalog_id), user)
            db.add(card)
            db.flush()  # assigns card.id
        card_ids.append(card.id)
    db.commit()
    created = save_from_source(db, DemoSource(card_ids), user)
    return {"cards": len(card_ids), "transactions_added": len(created)}


@router.post("/load")
def load_demo(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    """Add sample cards and purchases to your account."""
    return load_demo_data(db, user)


@router.post("/clear")
def clear_all(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    """Delete all of your cards, purchases and category fixes (your account stays)."""
    delete_user_data(db, user.id, sessions=False)  # stay logged in
    db.commit()
    return {"status": "cleared"}
