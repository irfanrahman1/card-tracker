"""'Load demo data' and 'Clear all data'."""
from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..ingest import save_from_source
from ..sources import DEMO_CARDS, DemoSource

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/load")
def load_demo(db: Session = Depends(get_db)):
    """Add the demo cards (if missing) and ~3 months of sample purchases.

    Safe to click more than once: existing demo cards and purchases are reused.
    """
    existing = {c.name: c for c in db.scalars(select(models.Card))}
    card_ids = []
    for spec in DEMO_CARDS:
        card = existing.get(spec["name"])
        if not card:
            card = models.Card(
                name=spec["name"], issuer=spec["issuer"], base_rate=spec["base_rate"],
                rules=[models.RewardRule(**r) for r in spec["rules"]],
            )
            db.add(card)
            db.flush()  # assigns card.id
        card_ids.append(card.id)
    db.commit()

    created = save_from_source(db, DemoSource(card_ids))
    return {"cards": len(card_ids), "transactions_added": len(created)}


@router.post("/clear")
def clear_all(db: Session = Depends(get_db)):
    """Delete every card and purchase. Handy for starting over."""
    db.execute(delete(models.Transaction))
    db.execute(delete(models.RewardRule))
    db.execute(delete(models.Card))
    db.commit()
    return {"status": "cleared"}
