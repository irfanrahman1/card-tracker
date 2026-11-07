"""Fallback parser for banks we don't have a parser for yet.

Looks for lines that look like a purchase:
    10/17   SAMS HALAL CART   NEW YORK NY      8.48
a date at the start, an amount at the end, words in between.
"""
import re

from ..csv_source import PAYMENT
from .text import AMOUNT, DATE, parse_amount, parse_date, statement_end_date

NAME = "generic"

# date, maybe a second date (posting date), maybe a * after a date, then the description, then the amount
LINE = re.compile(rf"^\s*({DATE})\*?\s+(?:{DATE}\*?\s+)?(.*?[A-Za-z].*?)\s+({AMOUNT})\s*$", re.IGNORECASE)

# summary lines on the statement that can look like purchases
SKIP_WORDS = [
    "balance", "minimum payment", "payment due", "credit limit", "available credit",
    "cash advance limit", "annual percentage", "closing date", "statement period",
    "statement date", "total fees", "total interest", "total purchases", "total payments",
    "total credits", "total for this period", "rewards earned",
]


def detects(text):
    return True  # it's the backup, so it takes anything


def parse(lines, skipped):
    end = statement_end_date(lines)
    rows = []
    for line in lines:
        match = LINE.match(line)
        if not match:
            continue
        date_text, description, amount_text = match.groups()
        description = " ".join(description.split())

        if any(word in description.lower() for word in SKIP_WORDS):
            continue
        if PAYMENT.search(description):
            skipped.append(description + ": card payment, not a purchase")
            continue
        try:
            date = parse_date(date_text, end)
            amount = parse_amount(amount_text)
        except ValueError as e:
            skipped.append(f"{description}: {e}")
            continue
        if amount == 0:
            continue

        rows.append({"date": date, "description": description, "amount": amount})
    return rows
