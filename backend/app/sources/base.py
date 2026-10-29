"""The interface every transaction source implements."""
from abc import ABC, abstractmethod

from ..schemas import TransactionIn


class TransactionSource(ABC):
    # Short label stored on each saved transaction ("manual", "csv", "plaid"...).
    name: str = "unknown"

    @abstractmethod
    def fetch(self) -> list[TransactionIn]:
        """Return the purchases this source provides."""
