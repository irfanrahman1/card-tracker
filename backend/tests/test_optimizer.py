"""Wallet optimizer: caps, fees, perks and suggestions."""
from app.optimizer import allocate, suggest, wallet_value


def card(key, base, rules=(), fee=0, credits=0, pv=1.0):
    return {"key": key, "name": key, "base_rate": base, "point_value": pv, "annual_fee": fee,
            "credits_value": credits, "rules": [dict(category=c, rate=r, cap=cap) for c, r, cap in rules]}


def test_spending_over_a_cap_falls_back_to_the_next_best_option():
    grocery = card("grocery", 1, [("groceries", 6, 6000)])
    flat = card("flat", 2)
    result = allocate([grocery, flat], {"groceries": 10000})
    # $6,000 at 6% = $360, remaining $4,000 at the flat card's 2% = $80
    assert round(result["rewards"], 2) == 440.00
    assert [u["card"] for u in result["per_category"]["groceries"]["cards"]] == ["grocery", "flat"]


def test_fees_and_perks_count_in_net_value():
    premium = card("premium", 1, [("travel", 5, None)], fee=895, credits=500)
    value = wallet_value([premium], {"travel": 4000})
    assert value["rewards"] == 200.00
    assert value["net"] == 200 - 895 + 500


def test_fees_category_is_never_optimized():
    assert allocate([card("flat", 2)], {"fees": 900})["rewards"] == 0


def test_suggests_the_card_that_adds_the_most_and_skips_owned_cards():
    owned = [card("flat", 2)]
    catalog = [card("flat", 2), card("dining", 1, [("food", 4, None)]), card("useless", 1)]
    result = suggest(owned, catalog, {"food": 5000, "other": 1000})
    assert [a["card"]["key"] for a in result["add"]] == ["dining"]  # gain: 5000 * (4% - 2%) = $100
    assert result["add"][0]["gain"] == 100.00


def rule(category, rate, cap=None, **extra):
    return dict(category=category, rate=rate, cap=cap, **extra)


def test_rotating_quarterly_rate_only_covers_a_quarter_of_the_year():
    discover = card("discover", 1)
    discover["rules"] = [rule("food", 5, 1500, portion=0.25, valid_until="2999-12-31")]
    result = allocate([discover], {"food": 4000})
    # $1,000 (a quarter) at 5% = $50, the other $3,000 at 1% = $30
    assert round(result["rewards"], 2) == 80.00


def test_shared_cap_is_used_up_across_categories():
    bofa = card("bofa", 1)
    bofa["rules"] = [rule("food", 3, 1000, cap_group="combined"), rule("groceries", 2, 1000, cap_group="combined")]
    result = allocate([bofa], {"food": 800, "groceries": 800})
    # food takes $800 of the $1,000 cap at 3% ($24); groceries gets the last $200 at 2% ($4)
    # and $600 at 1% ($6)
    assert round(result["rewards"], 2) == 34.00


def test_expired_rules_are_ignored():
    old = card("old", 1)
    old["rules"] = [rule("food", 5, valid_until="2000-03-31")]
    assert allocate([old], {"food": 100})["rewards"] == 1.00
