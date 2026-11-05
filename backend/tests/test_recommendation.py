"""Best-card ranking: rules beat base rates, and points are valued fairly against cash."""
from types import SimpleNamespace as Obj

from app.recommendation import best_card, rank_cards


def card(id, name, base, rules=(), reward_type="cash", point_value=1.0):
    return Obj(id=id, name=name, base_rate=base, reward_type=reward_type, point_value=point_value,
               rules=[Obj(category=c, rate=r) for c, r in rules])


def test_category_rule_beats_flat_card():
    cards = [card(1, "Flat 2%", 2), card(2, "Dining 4%", 1, [("food", 4)])]
    best = best_card(cards, "food", 50)
    assert best.card_name == "Dining 4%"
    assert best.reward == 2.00


def test_flat_card_wins_outside_bonus_category():
    cards = [card(1, "Flat 2%", 2), card(2, "Dining 4%", 1, [("food", 4)])]
    assert best_card(cards, "groceries", 100).card_name == "Flat 2%"


def test_points_are_compared_by_value_not_raw_rate():
    # 3x points worth 0.5c each (1.5c/$) should lose to 2% cash (2c/$).
    cards = [card(1, "Cash 2%", 2), card(2, "Points 3x", 1, [("food", 3)], "points", 0.5)]
    ranked = rank_cards(cards, "food", 100)
    assert [o.card_name for o in ranked] == ["Cash 2%", "Points 3x"]
    assert ranked[1].reward == 1.50


def test_no_cards_means_no_recommendation():
    assert best_card([], "food", 10) is None


def test_best_active_rule_wins_and_expired_rules_are_skipped():
    from datetime import date
    flex = card(1, "Flex", 1, [("food", 3), ("food", 7)])
    flex.rules[1].valid_until = "2026-12-31"
    assert best_card([flex], "food", 100).rate == 7
    assert rank_cards([flex], "food", 100)[0].rate == 7
    from app.recommendation import rate_for
    assert rate_for(flex, "food", today=date(2027, 1, 1))[0] == 3
