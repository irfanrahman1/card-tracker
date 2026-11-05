"""Sample cards and ~3 months of sample purchases for trying the app out."""
import random
from datetime import date, timedelta

from ..schemas import TransactionIn
from .base import TransactionSource

# Popular cards from the catalog (catalog/cards.json) for the demo wallet.
DEMO_CARD_IDS = ["amex-gold", "chase-freedom-unlimited", "citi-double-cash", "amex-blue-cash-preferred"]

# (merchant, low $, high $, how often). No categories given: the app guesses them.
DEMO_MERCHANTS = [
    ("Whole Foods Market", 30, 140, 4), ("Trader Joe's", 20, 90, 4), ("Safeway", 15, 80, 3),
    ("Chipotle", 10, 18, 4), ("Starbucks", 4, 9, 5), ("Joe's Pizza", 12, 35, 3), ("DoorDash", 20, 55, 3),
    ("Amazon", 10, 120, 5), ("Amazon Fresh", 30, 90, 2), ("Target", 15, 100, 2), ("Best Buy", 25, 300, 1),
    ("Uber", 9, 35, 3), ("Shell Gas", 30, 65, 2), ("MTA NYCT Paygo", 2.9, 2.9, 5), ("Lyft", 8, 30, 2),
    ("Netflix", 15.49, 15.49, 1), ("Spotify", 11.99, 11.99, 1), ("CVS Pharmacy", 5, 40, 2),
    ("Delta Air Lines", 180, 420, 1), ("Marriott Hotel", 150, 320, 1), ("City Dry Cleaners", 12, 30, 1),
]

class DemoSource(TransactionSource):
    name = "demo"

    def __init__(self, card_ids: list[int], today: date | None = None, count: int = 90):
        self.card_ids = card_ids
        # Sample purchases end on the last day of last month, so the demo opens on a full month.
        self.today = today or (date.today().replace(day=1) - timedelta(days=1))
        self.count = count

    def fetch(self) -> list[TransactionIn]:
        rng = random.Random(42)  # fixed seed: same demo data every time
        results = []
        for i in range(self.count):
            merchant, low, high, _ = rng.choices(DEMO_MERCHANTS, weights=[m[3] for m in DEMO_MERCHANTS])[0]
            results.append(TransactionIn(
                date=self.today - timedelta(days=rng.randint(0, 89)),
                merchant=merchant,
                amount=round(rng.uniform(low, high), 2),
                # Random card, so some purchases use the "wrong" one and the app can show
                # what the best card would have earned.
                card_id=rng.choice(self.card_ids) if self.card_ids else None,
                external_id=f"demo-{i}",  # lets "Load demo data" run twice without duplicates
            ))
        return results
