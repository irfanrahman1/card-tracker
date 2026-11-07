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
