"""Wallet optimizer: which cards earn you the most for how you actually spend?

Given a year of spending per category and a set of cards, it works out the
best card for every dollar, respecting yearly caps (e.g. "4x on groceries up
to $25k/yr"), then subtracts annual fees and adds the value of perks you use.

Plain Python with no web or database code, like recommendation.py. Cards are
plain dicts here so catalog cards and your own cards are handled the same way:
    {"key", "name", "base_rate", "point_value", "annual_fee", "credits_value",
     "rules": [{"category", "rate", "cap"}]}
"""
from itertools import combinations

# Fees aren't rewarded spending, so they're left out of the optimization.
SKIP_CATEGORIES = {"fees"}


def _value_options(cards: list[dict], category: str) -> list[dict]:
    """Every way to earn in this category: each card's bonus rate (maybe capped)
    and its uncapped base rate, as cents per dollar. Best first."""
    options = []
    for card in cards:
        options.append({"card": card, "cents": card["base_rate"] * card["point_value"], "cap": None})
        for rule in card["rules"]:
            if rule["category"] == category and rule["rate"] > card["base_rate"]:
                options.append({"card": card, "cents": rule["rate"] * card["point_value"], "cap": rule.get("cap")})
    return sorted(options, key=lambda o: -o["cents"])


def allocate(cards: list[dict], spending: dict[str, float]) -> dict:
    """Assign each category's spending to the best card(s), filling caps greedily.

    Greedy is optimal here: within one category, every dollar should go to the
    highest-value option that still has room under its cap.
    """
    per_category = {}
    total = 0.0
    for category, spend in spending.items():
        if category in SKIP_CATEGORIES or spend <= 0:
            continue
        remaining, rewards, used = spend, 0.0, []
        for option in _value_options(cards, category):
            if remaining <= 0:
                break
            portion = remaining if option["cap"] is None else min(remaining, option["cap"])
            if portion <= 0:
                continue
            rewards += portion * option["cents"] / 100
            used.append({"card": option["card"]["name"], "spend": round(portion, 2),
                         "cents_per_dollar": round(option["cents"], 3)})
            remaining -= portion
        per_category[category] = {"spend": round(spend, 2), "rewards": round(rewards, 2), "cards": used}
        total += rewards
    return {"rewards": total, "per_category": per_category}


def wallet_value(cards: list[dict], spending: dict[str, float]) -> dict:
    """Yearly rewards minus fees plus perks for a set of cards."""
    alloc = allocate(cards, spending)
    fees = sum(c["annual_fee"] for c in cards)
    credits = sum(c["credits_value"] for c in cards)
    return {
        "rewards": round(alloc["rewards"], 2),
        "fees": round(fees, 2),
        "credits": round(credits, 2),
        "net": round(alloc["rewards"] - fees + credits, 2),
        "per_category": alloc["per_category"],
    }


def suggest(owned: list[dict], catalog: list[dict], spending: dict[str, float], top: int = 5) -> dict:
    """Current wallet value, the best cards to add, and the best 1- and 2-card wallets."""
    current = wallet_value(owned, spending)
    owned_keys = {c["key"] for c in owned}
    candidates = [c for c in catalog if c["key"] not in owned_keys]

    additions = []
    for card in candidates:
        with_card = wallet_value(owned + [card], spending)
        additions.append({
            "card": card,
            "gain": round(with_card["net"] - current["net"], 2),
            "new_net": with_card["net"],
        })
    additions.sort(key=lambda a: -a["gain"])

    # Best wallets from scratch (owned + catalog), to answer "what should I carry?"
    pool = owned + candidates
    best_single = max(pool, key=lambda c: wallet_value([c], spending)["net"], default=None)
    best_pair = max(combinations(pool, 2), key=lambda p: wallet_value(list(p), spending)["net"], default=None)

    return {
        "current": current,
        "add": [a for a in additions[:top] if a["gain"] > 0],
        "best_single": best_single and {"cards": [best_single], **wallet_value([best_single], spending)},
        "best_pair": best_pair and {"cards": list(best_pair), **wallet_value(list(best_pair), spending)},
    }
