""""Best card for this purchase" logic.

Kept in its own file with no web or database code, so it's easy to read,
test and change. It works on any card-like object with .name, .base_rate,
.rules and optionally .reward_type / .point_value.

Cards are compared by *value per dollar* in cents: rate x point value.
  - 3% cash back             -> 3 x 1.0 = 3.0 cents per dollar
  - 4 points/$ at 1.25c/point -> 4 x 1.25 = 5.0 cents per dollar
So a points card and a cash card can be compared fairly.
"""
from dataclasses import dataclass
from datetime import date


@dataclass
class CardOption:
    card_id: int
    card_name: str
    rate: float           # points or % per dollar for this purchase, e.g. 4.0
    cents_per_dollar: float  # value per dollar spent, e.g. 4.0 points x 1.25c = 5.0
    reward: float         # dollars back for this purchase
    reason: str           # human-readable explanation, e.g. "4x on food"


def point_value(card) -> float:
    """Cents per point. Cash-back cards are always 1 cent per 1%."""
    if getattr(card, "reward_type", "cash") == "cash":
        return 1.0
    return getattr(card, "point_value", 1.0) or 1.0


def is_active(rule, today: date | None = None) -> bool:
    """False once a time-limited rule (e.g. last quarter's rotating 5%) has ended."""
    until = getattr(rule, "valid_until", None)
    return not until or until >= (today or date.today()).isoformat()


def rate_for(card, category: str, today: date | None = None) -> tuple[float, str]:
    """Return (rate, reason) for one card in one category today (ignores yearly caps).

    The best active rule for the category wins; otherwise the card's base rate applies.
    If a rule is somehow lower than the base rate, the base rate is used.
    """
    unit = "x" if getattr(card, "reward_type", "cash") == "points" else "%"
    rules = [r for r in card.rules if r.category == category and is_active(r, today) and r.rate >= card.base_rate]
    if rules:
        rule = max(rules, key=lambda r: r.rate)
        until = getattr(rule, "valid_until", None)
        return rule.rate, f"{rule.rate:g}{unit} on {category}" + (f" until {until}" if until else "")
    return card.base_rate, f"{card.base_rate:g}{unit} base rate"


def rank_cards(cards, category: str, amount: float) -> list[CardOption]:
    """Every card's reward for this purchase, best first (ties sorted by name)."""
    options = []
    for card in cards:
        rate, reason = rate_for(card, category)
        cents = rate * point_value(card)
        if getattr(card, "reward_type", "cash") == "points" and point_value(card) != 1.0:
            reason += f" (points at {point_value(card):g}¢)"
        options.append(CardOption(
            card_id=card.id,
            card_name=card.name,
            rate=rate,
            cents_per_dollar=round(cents, 3),
            reward=round(amount * cents / 100, 2),
            reason=reason,
        ))
    return sorted(options, key=lambda o: (-o.cents_per_dollar, o.card_name.lower()))


def best_card(cards, category: str, amount: float) -> CardOption | None:
    """The single best card, or None if there are no cards."""
    ranked = rank_cards(cards, category, amount)
    return ranked[0] if ranked else None
