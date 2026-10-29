"""Spending categories and the rules for assigning a purchase to one.

Every purchase ends up in exactly one of CATEGORIES. The order of checks:
  1. Anything from Amazon is "shopping".
  2. A category label we understand (ours, or a bank's like "Food & Drink").
  3. Keywords in the merchant name ("halal", "OMNY", "Booking.com"...).
  4. Otherwise "other".
Categories you fix by hand in the app are remembered per merchant (see ingest.py)
and take priority over steps 2-4 for future imports.
"""
import re

# Order matters for display (and chart colors are assigned in this order).
CATEGORIES = [
    "food", "transportation", "groceries", "shopping",
    "travel", "subscriptions", "fees", "other",
]

# Merchant-name keywords, matched as whole words, case-insensitive.
# Checked top to bottom: the first category with a match wins. So "uber eats"
# (food) and "uber one" (subscriptions) are caught before plain "uber" (transportation).
KEYWORDS = {
    "fees": [
        "membership fee", "annual fee", "late fee", "interest charge", "foreign transaction fee",
    ],
    "subscriptions": [
        "netflix", "hulu", "disney plus", "disney+", "peacock", "max.com", "hbo max", "paramount+",
        "spotify", "apple.com/bill", "youtube premium", "youtube tv", "audible", "uber one",
        "walmart+", "dashpass", "openai", "chatgpt", "anthropic", "claude.ai", "walter ai",
        "notion", "dropbox", "icloud", "google one", "adobe", "microsoft 365", "github",
        "entertainment credit", "digital entertainment", "nytimes", "new york times",
        "planet fitness", "equinox", "crunch fitness",
    ],
    "travel": [
        "booking.com", "expedia", "hotels.com", "airbnb", "vrbo", "hotel", "hotels", "inn", "resort",
        "marriott", "hilton", "hyatt", "ihg", "getyourguide", "viator", "klook", "tripadvisor",
        "airline", "airlines", "airways", "air maroc", "delta air", "united airlines", "american air",
        "jetblue", "southwest", "spirit airl", "frontier airl", "alaska air", "emirates", "qatar",
        "turkish airl", "lufthansa", "british a", "air france", "klm", "ryanair", "easyjet",
        "amtrak", "greyhound", "flixbus", "hertz", "avis", "enterprise rent", "budget rent",
        "travel", "airport",
    ],
    "shopping": [
        "amazon", "amzn", "target", "walmart", "wal-mart", "best buy", "ebay", "etsy", "ikea",
        "temu", "shein", "uniqlo", "zara", "h&m", "nike", "adidas", "macy's", "macys", "nordstrom",
        "tj maxx", "tjmaxx", "marshalls", "sephora", "ulta", "home depot", "lowe's", "lowes",
        "staples", "old navy", "gap", "american eagle", "lululemon", "apple store", "barnes",
        "muji", "urban outfitters", "duane reade", "cvs", "walgreens", "rite aid",
    ],
    "groceries": [
        "grocery", "groceries", "supermarket", "superma", "supermkt", "whole foods", "wholefds",
        "trader joe", "trader joe's", "safeway", "kroger", "costco", "aldi", "wegmans", "publix",
        "heb", "h-e-b", "fairway", "key food", "food bazaar", "ctown", "c-town", "stop & shop",
        "shoprite", "h mart", "hmart", "sprouts", "food lion", "gristedes", "morton william",
        "morton williams", "morton willia", "instacart", "fresh direct", "freshdirect",
        "trade fair", "bazar", "bazaar", "fruit", "frui", "produce", "mini mart", "mini ma", "conven",
        "market", "marke", "mkt", "premium super",
    ],
    "food": [
        "restaurant", "restaura", "restaur", "restau", "cafe", "café", "coffee", "coff", "starbucks", "dunkin", "pizza",
        "burger", "bur", "grill", "deli", "delic", "halal", "kitchen", "taco", "tacos", "ramen",
        "sushi", "thai", "pho", "noodle", "bakery", "bagel", "bagels", "bistro", "diner", "eatery",
        "bar", "pub", "tavern", "brewery", "chicken", "hot chi", "wings", "gyro", "kebab",
        "falafel", "dumpling", "poke", "boba", "tea", "mediterranean", "mokafe",
        "chipotle", "mcdonald's", "mcdonalds", "wendy's", "taco bell", "kfc", "popeyes",
        "chick-fil-a", "five guys", "shake shack", "sweetgreen", "cava", "panera", "domino's",
        "dominos", "papa john", "subway", "joe & the juice", "pret", "levy", "paris baguette",
        "doordash", "grubhub", "seamless", "uber eats", "ubereats", "postmates", "caviar",
    ],
    "transportation": [
        "uber", "lyft", "taxi", "cab", "mta", "nyct", "omny", "omnyweb", "omnyautoload", "metrocard",
        "nj transit", "njt", "path tapp", "lirr", "citi bike", "citibike", "lime", "revel",
        "parking", "toll", "e-zpass", "ezpass", "shell", "chevron", "exxon", "exxonmobil", "mobil",
        "bp", "sunoco", "speedway", "citgo", "gas", "fuel", "transit", "metro",
    ],
}
# "subway" sits in food on purpose: card statements call the NYC subway "NYCT"/"OMNY".

# Bank category labels -> ours, matched as substrings of the bank's label, top to bottom.
# Covers labels from Amex, Chase, Capital One, Discover, Citi and Apple Card.
BANK_LABELS = [
    ("fees", ["fees & adjustments", "fees and adjustments", "annual fee", "membership fee"]),
    ("groceries", ["grocer", "supermarket"]),
    ("food", ["restaurant", "dining", "food & drink", "food and drink", "fast food", "coffee", "bar & caf"]),
    ("travel", ["airline", "airfare", "lodging", "hotel", "travel", "car rental"]),
    ("transportation", ["gas", "fuel", "transport", "parking", "taxi", "rideshare", "transit",
                        "automotive", "toll"]),
    ("subscriptions", ["subscription", "streaming"]),
    ("shopping", ["shopping", "merchandise", "retail", "department store", "clothing", "electronics",
                  "home improvement", "pharmac"]),
]

# Old/other names people use for our categories (e.g. in a hand-made CSV).
ALIASES = {
    "dining": "food", "restaurants": "food", "grocery": "groceries", "transit": "transportation",
    "gas": "transportation", "subscription": "subscriptions", "fee": "fees", "card fees": "fees",
}

# Prefixes that card networks and payment terminals add to merchant names.
PREFIXES = re.compile(
    r"^(aplpay|apple ?pay|gglpay|google ?pay|sq ?\*|tst ?\*|sp ?\*|py ?\*|paypal ?\*|"
    r"bt ?\*|pp ?\*|cke ?\*|toast ?\*|clover ?\*)\s*",
    re.IGNORECASE,
)

_patterns = {
    category: re.compile(
        r"(?<![\w])(" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")(?![\w])",
        re.IGNORECASE,
    )
    for category, words in KEYWORDS.items()
}


def clean_merchant(name: str) -> str:
    """'AplPay SAMS HALAL CART' -> 'SAMS HALAL CART'. Removes payment prefixes and extra spaces."""
    name = " ".join((name or "").split())
    for _ in range(2):  # some have two, e.g. "AplPay TST* JOE COFF"
        name = PREFIXES.sub("", name)
    return name.strip() or "Unknown"


def guess_category(text: str) -> str | None:
    """Guess a category from a merchant name like 'SAMS HALAL CART', or None if no keyword matches."""
    lowered = (text or "").lower()
    if re.search(r"(^|\s)tst ?\*", lowered):  # "TST*" = Toast, a restaurant payment terminal
        return "food"
    for category, pattern in _patterns.items():
        if pattern.search(lowered):
            return category
    return None


def category_from_label(label: str | None) -> str | None:
    """Turn our own or a bank's category label into one of CATEGORIES, or None if unknown."""
    cleaned = (label or "").strip().lower()
    if not cleaned:
        return None
    if cleaned in CATEGORIES:
        return cleaned
    if cleaned in ALIASES:
        return ALIASES[cleaned]
    for category, words in BANK_LABELS:
        if any(word in cleaned for word in words):
            return category
    return None


def is_amazon(text: str) -> bool:
    return bool(re.search(r"amazon|amzn", text or "", re.IGNORECASE))


def normalize_category(category: str | None, merchant: str = "", description: str = "") -> str:
    """Return one of CATEGORIES (see the order of checks at the top of this file).

    The merchant name is checked before the description, since descriptions often hold a
    city ("UNITED STATES") that would otherwise match a keyword.
    """
    if is_amazon(merchant) or is_amazon(description):
        return "shopping"
    return (
        category_from_label(category)
        or guess_category(merchant)
        or guess_category(description)
        or "other"
    )
