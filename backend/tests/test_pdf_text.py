"""Reading text out of PDF statements. Every PDF here is made up (see pdf_maker.py):
real statements never go in the repo."""
from datetime import date

import pytest

from app.sources.pdf.text import extract_lines, parse_amount, parse_date, statement_end_date

from .pdf_maker import make_pdf

STATEMENT = make_pdf([
    "Some Bank Card                       Closing Date 12/31/26",
    "Payment Due Date 01/25/2027",
    "12/03  TRADER JOE'S #552  NEW YORK NY            54.20",
])


def test_text_comes_out_line_by_line_with_columns_kept():
    lines = extract_lines(STATEMENT)
    trader = next(line for line in lines if "TRADER" in line)
    assert trader.split()[0] == "12/03" and trader.split()[-1] == "54.20"
    assert "TRADER JOE'S" in trader  # curly quote from the PDF font is straightened


def test_closing_date_beats_other_dates():
    assert statement_end_date(extract_lines(STATEMENT)) == date(2026, 12, 31)


def test_dates_without_a_year_use_the_closing_date():
    end = date(2027, 1, 3)
    assert parse_date("12/28", end) == date(2026, 12, 28)  # December on a January statement
    assert parse_date("01/02", end) == date(2027, 1, 2)
    assert parse_date("Dec 28", end) == date(2026, 12, 28)
    assert parse_date("10/17/26", end) == date(2026, 10, 17)


def test_amount_formats():
    assert parse_amount("$1,234.56") == 1234.56
    for credit in ("-$5.00", "($5.00)", "5.00 CR", "5.00-", "−5.00"):
        assert parse_amount(credit) == -5.0, credit


@pytest.mark.parametrize("content, message", [
    (b"not a pdf at all", "Couldn't read this file as a PDF"),
    (make_pdf([]), "no text in it"),
])
def test_unreadable_pdfs_give_a_clear_message(content, message):
    with pytest.raises(ValueError, match=message):
        extract_lines(content)
