"""Purchases typed in by the user through the form."""
from ..schemas import TransactionIn
from .base import TransactionSource


class ManualSource(TransactionSource):
    name = "manual"

    def __init__(self, transactions: list[TransactionIn]):
        self.transactions = transactions

    def fetch(self) -> list[TransactionIn]:
        # Already validated by the API layer, so just hand them back.
        return self.transactions
