"""Tests for the Amex parser. Everything here is made up (fake names, fake purchases),
laid out the way the two kinds of Amex PDFs come out as text."""
from datetime import date

from app.sources.pdf import PDFSource

from .pdf_maker import make_pdf

# The regular Amex PDF: amounts are on their own line, a few lines under the date
REGULAR = [
    "Platinum Card",
    "JANE DOE",
    "Closing Date 10/18/26",
    "Website: americanexpress.com",
    "JANE DOE Account Ending 1-23456",
    "Payments $0.00 -$500.00 -$500.00",
    "Total Payments and Credits $0.00 -$520.00 -$520.00",
    "Payments Amount",
    "10/12/26* JANE DOE AUTOPAY PAYMENT RECEIVED - THANK YOU",
    "SOME BANK, NA",
    "-$500.00",
    "Credits Amount",
    "10/02/26 JANE DOE Platinum Uber One Credit",
    "UBER ONE",
    "-$9.99",
    "10/16/26* JANE DOE CR ADJ - ANNUAL FEE -$10.01",
    "Total New Charges $0.00 $1,055.48 $1,055.48",
    "JANE DOE",
    "Card Ending 1-23456 Foreign",
    "Spend Amount",
    "09/20/26 SOME AIRLINE NEW YORK NY",
    "Ticket Number: 123 Date of Departure: 01/04",
    "$1,000.00",
    "09/21/26 HOTEL ON BOOKING.COM AMSTERDAM NL",
    "248,94",
    "European UnionEuro",
    "$52.48",
    "JOHN DOE",
    "Card Ending 1-23464 Foreign",
    "Spend Amount",
    "10/05/26 NYCT PAYGO NEW YORK NY",
    "LOCAL TRANSPORTATION",
    "$3.00",
    "Fees Amount",
    "10/16/26 JANE DOE ANNUAL FEE",
    "Cover your annual fee using points.",
    "$100.00",
    "Total Fees for this Period $100.00",
    "Total Interest Charged for this Period $0.00",
]

# The "screen reader optimized" PDF: one line per purchase, with a Type column
SCREEN_READER = [
    "Closing Date 10/18/26     Account Ending 1-23456",
    "Visit americanexpress.com",
    "Payments          $0.00      -$500.00      -$500.00",
    "Total Payments and Credits      $0.00      -$520.00      -$520.00",
    "JANE DOE",
    "Card Ending 1-23456",
    "10/12/26*     AUTOPAY PAYMENT RECEIVED - THANK YOU                     -$500.00",
    "10/02/26      Platinum Uber One Credit           Pay Over Time        -$9.99",
    "10/16/26*     CR ADJ - ANNUAL FEE                Pay Over Time       -$10.01",
    "Total New Charges        $0.00       $1,055.48       $1,055.48",
    "09/20/26      SOME AIRLINE  NEW YORK  NY         Pay Over Time    $1,000.00",
    "09/21/26      HOTEL ON BOOKING.COM  AMSTERDAM  NL   Pay Over Time   248,94   $52.48",
    "JOHN DOE",
    "Card Ending 1-23464",
    "10/05/26      NYCT PAYGO  NEW YORK  NY           Pay Over Time        $3.00",
    "10/16/26      JANE DOE      ANNUAL FEE           Pay Over Time      $100.00",
    "Total Fees for this Period                                         $100.00",
    "Total Interest Charged for this Period                               $0.00",
]

EXPECTED = [
    (date(2026, 10, 2), "Platinum Uber One Credit", -9.99),
    (date(2026, 10, 16), "CR ADJ - ANNUAL FEE", -10.01),
    (date(2026, 9, 20), "SOME AIRLINE NEW YORK NY", 1000.00),
    (date(2026, 9, 21), "HOTEL ON BOOKING.COM AMSTERDAM NL", 52.48),
    (date(2026, 10, 5), "NYCT PAYGO NEW YORK NY", 3.00),
    (date(2026, 10, 16), "ANNUAL FEE", 100.00),
]


def read(lines):
    source = PDFSource(make_pdf(lines))
    rows = source.fetch()
    return source, [(r.date, r.merchant, r.amount) for r in rows]


def test_regular_amex_pdf():
    source, rows = read(REGULAR)
    assert source.parser_name == "amex"
    assert rows == EXPECTED
    assert len(source.skipped) == 1 and "AUTOPAY PAYMENT" in source.skipped[0]  # the payment isn't a purchase


def test_screen_reader_amex_pdf_gives_the_same_rows():
    source, rows = read(SCREEN_READER)
    assert source.parser_name == "amex"
    assert rows == EXPECTED


def test_both_versions_give_same_ids_so_no_duplicates():
    regular = [r.external_id for r in PDFSource(make_pdf(REGULAR)).fetch()]
    screen_reader = [r.external_id for r in PDFSource(make_pdf(SCREEN_READER)).fetch()]
    assert regular == screen_reader


def test_totals_match_the_statement():
    source, _ = read(REGULAR)
    assert source.totals_checked
    assert source.warnings == []


def test_warning_when_totals_dont_match():
    lines = [line.replace("$1,055.48", "$1,099.00") for line in REGULAR]
    source, _ = read(lines)
    assert source.warnings == ["Purchases add up to $1,155.48 but the statement says $1,199.00."]
