"""CSV import (bank formats, payments, refunds) and automatic categories."""
from app.categories import clean_merchant, normalize_category
from app.sources.csv_source import CSVSource

AMEX = b"""Date,Description,Card Member,Account #,Amount
10/17/2026,AplPay SAMS HALAL CANEW YORK            NY,A PERSON,-11111,8.48
10/16/2026,AMAZON MARKETPLACE NAMZN.COM/BILL       WA,A PERSON,-11111,-23.94
10/12/2026,AUTOPAY PAYMENT - THANK YOU,A PERSON,-11111,-1680.80
10/10/2026,NYCT PAYGO          NEW YORK            NY,A PERSON,-11111,3.00
"""

CHASE = b"""Transaction Date,Post Date,Description,Category,Type,Amount,Memo
10/03/2026,10/04/2026,TRADER JOE'S #552,Groceries,Sale,-54.20,
10/05/2026,10/05/2026,Payment Thank You-Mobile,,Payment,500.00,
10/06/2026,10/07/2026,TARGET 00012,Shopping,Return,12.00,
"""


def parse(content):
    source = CSVSource(content, {})
    return source.fetch(), source.skipped


def test_amex_export_payments_skipped_refunds_negative():
    rows, skipped = parse(AMEX)
    assert len(rows) == 3 and len(skipped) == 1  # the autopay row
    halal, amazon, subway = rows
    assert halal.merchant == "AplPay SAMS HALAL CA" and halal.description == "NEW YORK NY"
    assert amazon.amount == -23.94  # refund
    assert subway.amount == 3.00


def test_chase_export_negative_purchases_are_flipped():
    rows, skipped = parse(CHASE)
    assert [r.amount for r in rows] == [54.20, -12.00]  # sale, then return as a refund
    assert len(skipped) == 1


def test_uploading_the_same_file_gives_the_same_ids():
    assert [r.external_id for r in parse(AMEX)[0]] == [r.external_id for r in parse(AMEX)[0]]


def test_categories_from_real_world_merchant_names():
    cases = {
        "AplPay SAMS HALAL CA": "food",
        "AplPay TST* PARIS BA": "food",           # TST* = restaurant terminal
        "NYCT PAYGO": "transportation",
        "HOTEL ON BOOKING.COM": "travel",
        "OPENAI *CHATGPT SUBS": "subscriptions",
        "RENEWAL MEMBERSHIP FEE": "fees",
        "AplPay TRADE FAIR #1": "groceries",
        "Amazon Fresh": "shopping",              # Amazon always counts as shopping
        "GOFUNDME": "other",
    }
    for merchant, expected in cases.items():
        assert normalize_category(None, merchant) == expected, merchant


def test_bank_category_label_is_used_and_prefixes_are_cleaned():
    assert normalize_category("Food & Drink", "SOME PLACE") == "food"
    assert normalize_category("Merchandise & Supplies-Groceries", "X") == "groceries"
    assert clean_merchant("AplPay TST* JOE COFF") == "JOE COFF"
