""""Best card for this purchase" logic.

Kept in its own file with no web or database code, so it's easy to read,
test and change. It works on plain Card objects (anything with .name,
.base_rate and .rules).
"""
from dataclasses import dataclass


@dataclass
class CardOption:
    card_id: int
    card_name: str
    rate: float      # percent back for this purchase, e.g. 3.0
    reward: float    # dollars back for this purchase (rate x amount)
    reason: str      # human-readable explanation, e.g. "4% on groceries"


def rate_for(card, category: str) -> tuple[float, str]:
    """Return (rate, reason) for one card in one category.

    A category rule wins if the card has one; otherwise the card's base rate applies.
    If a rule is somehow lower than the base rate, the base rate is used.
    """
    for rule in card.rules:
        if rule.category == category and rule.rate >= card.base_rate:
            return rule.rate, f"{rule.rate:g}% on {category}"
    return card.base_rate, f"{card.base_rate:g}% base rate"


def rank_cards(cards, category: str, amount: float) -> list[CardOption]:
    """Every card's reward for this purchase, best first (ties sorted by name)."""
    options = []
    for card in cards:
        rate, reason = rate_for(card, category)
        options.append(CardOption(
            card_id=card.id,
            card_name=card.name,
            rate=rate,
            reward=round(amount * rate / 100, 2),
            reason=reason,
        ))
    return sorted(options, key=lambda o: (-o.rate, o.card_name.lower()))


def best_card(cards, category: str, amount: float) -> CardOption | None:
    """The single best card, or None if there are no cards."""
    ranked = rank_cards(cards, category, amount)
    return ranked[0] if ranked else None
