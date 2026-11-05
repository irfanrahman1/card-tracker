"""Transaction sources.

Every way of getting purchases into the app (manual entry, CSV upload, demo
data, and later Plaid) is a TransactionSource. Each one only has to turn its
raw input into a list of TransactionIn; saving, category clean-up and
de-duplication are shared and live in ingest.py.

To add Plaid later: create sources/plaid.py with a PlaidSource class that
implements fetch() using the Plaid API, then call ingest.save_from_source()
with it from a new route. Nothing else needs to change.
"""
from .base import TransactionSource
from .csv_source import CSVSource
from .demo import DEMO_CARD_IDS, DemoSource
from .manual import ManualSource

__all__ = ["TransactionSource", "CSVSource", "DemoSource", "DEMO_CARD_IDS", "ManualSource"]
