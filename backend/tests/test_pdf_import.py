"""Tests for the PDF importer. The statement here is made up, not a real one."""
from datetime import date

import pytest

from app.sources.pdf import PDFSource, pick_parser

from .pdf_maker import make_pdf

FAKE_STATEMENT = make_pdf(
    [
        "Some Bank Platinum Card                    Account ending 1234",
        "Statement period 12/01/2026 - 12/31/2026",
        "New Balance                                          $1,302.87",
        "Payment Due Date 01/25/2027             Minimum Payment $35.00",
        "Trans  Post   Description                              Amount",
        "12/03  12/04  TRADER JOE'S #552  NEW YORK NY            54.20",
        "12/05* 12/05  AUTOPAY PAYMENT - THANK YOU            -500.00",
        "12/06  12/07* TARGET 00012 RETURN                      -12.00",
    ],
    [
        "12/28  12/29  DELTA AIR LINES  ATLANTA GA            1,240.67",
        "12/30  12/30  STARBUCKS (STORE 9)                        6.25",
        "Total fees for this period                               $0.00",
    ],
)


def test_generic_parser():
    source = PDFSource(FAKE_STATEMENT, default_card_id=7)
    rows = source.fetch()
    assert source.parser_name == "generic"
    assert [(r.date, r.merchant, r.amount) for r in rows] == [
        (date(2026, 12, 3), "TRADER JOE'S #552 NEW YORK NY", 54.20),
        (date(2026, 12, 6), "TARGET 00012 RETURN", -12.00),  # refund is negative
        (date(2026, 12, 28), "DELTA AIR LINES ATLANTA GA", 1240.67),
        (date(2026, 12, 30), "STARBUCKS (STORE 9)", 6.25),
    ]
    assert rows[0].card_id == 7
    assert source.skipped == ["AUTOPAY PAYMENT - THANK YOU: card payment, not a purchase"]


def test_same_pdf_gives_same_ids():
    first = [r.external_id for r in PDFSource(FAKE_STATEMENT).fetch()]
    second = [r.external_id for r in PDFSource(FAKE_STATEMENT).fetch()]
    assert first == second


class FakeBank:
    NAME = "fakebank"

    def detects(self, text):
        return "Some Bank Platinum" in text

    def parse(self, lines, skipped):
        return [{"date": date(2026, 12, 1), "description": "FROM FAKEBANK", "amount": 1.0}]


def test_bank_parser_is_used_when_it_matches():
    source = PDFSource(FAKE_STATEMENT, parsers=[FakeBank()])
    assert [r.merchant for r in source.fetch()] == ["FROM FAKEBANK"]
    assert source.parser_name == "fakebank"
    assert pick_parser("some other bank", [FakeBank()]).NAME == "generic"


def test_pdf_with_no_purchases():
    with pytest.raises(ValueError, match="Couldn't find any purchases"):
        PDFSource(make_pdf(["Hello, this page has no purchases on it."])).fetch()


# A made-up bank that wraps long descriptions and puts the amount on its own line
WRAPPED = make_pdf([
    "Other Bank Rewards Card",
    "Previous Balance                                      $200.00",
    "New Balance                                           $550.50",
    "11/02/26  CITY HARDWARE STORE",
    "          BROOKLYN NY",
    "          $45.50",
    "11/05/26  SOME AIRLINE",
    "          Ticket 123  Departs 01/04",
    "          $310.00",
    "11/09/26  ONLINE PAYMENT THANK YOU",
    "          -$100.00",
    "11/12/26  COFFEE PLACE  NEW YORK NY      $95.00",
])


def test_amount_on_a_line_below_the_date():
    source = PDFSource(WRAPPED)
    rows = source.fetch()
    assert [(r.date, r.merchant, r.amount) for r in rows] == [
        (date(2026, 11, 2), "CITY HARDWARE STORE", 45.50),
        (date(2026, 11, 5), "SOME AIRLINE", 310.00),
        (date(2026, 11, 12), "COFFEE PLACE NEW YORK NY", 95.00),
    ]
    assert source.skipped == ["ONLINE PAYMENT THANK YOU: card payment, not a purchase"]


def test_balance_check_passes_when_everything_adds_up():
    # 45.50 + 310.00 + 95.00 - 100.00 = 350.50, and 550.50 - 200.00 = 350.50
    source = PDFSource(WRAPPED)
    source.fetch()
    assert source.totals_checked
    assert source.warnings == []


def test_balance_check_warns_when_something_is_missing():
    source = PDFSource(make_pdf([
        "Previous Balance $200.00",
        "New Balance $350.50",
        "11/12/26  COFFEE PLACE  NEW YORK NY      $95.00",
    ]))
    source.fetch()
    assert source.warnings == [
        "Everything we read adds up to $95.00, but the balance changed by $150.50. Some purchases may be missing."
    ]


def test_no_balances_on_statement_means_not_checked():
    source = PDFSource(FAKE_STATEMENT)  # it has a New Balance but no Previous Balance
    source.fetch()
    assert not source.totals_checked
