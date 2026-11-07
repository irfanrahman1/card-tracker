"""American Express statements (the regular PDF and the "screen reader optimized" one).

The generic reader already finds the purchases. Amex just needs two extra things:
  - cleaning: Amex puts the cardholder's name in front of some purchases
    ("JANE DOE AUTOPAY PAYMENT") and the screen reader PDF adds a "Pay Over Time" column
  - a totals check using Amex's own totals (Total New Charges, Total Fees...), because
    the regular PDF doesn't print the balances on the same line as their labels
"""
import re

from . import generic
from .text import parse_amount

NAME = "amex"

MONEY = re.compile(r"-?\$[\d,]+\.\d{2}")  # e.g. $6,319.62 or -$23.94


def detects(text):
    # Amex prints its website on its own statements. Just "American Express" isn't
    # enough: another bank's statement could show a payment to American Express.
    return "americanexpress.com" in text.lower()


def cardholder_names(lines):
    # the name is on the line above "Card Ending ...", or before "Account Ending ..."
    names = []
    for i in range(len(lines)):
        line = " ".join(lines[i].split())
        if line.startswith("Card Ending") and i > 0:
            names.append(" ".join(lines[i - 1].split()))
        if " Account Ending" in line:
            names.append(line.split(" Account Ending")[0])
    # drop anything with a number in it (like "Closing Date 10/18/26"), that's not a name
    return [name for name in names if name and not re.search(r"\d", name)]


def clean_description(text, names):
    text = text.split("Pay Over Time")[0].strip()
    for name in names:
        if text.upper().startswith(name.upper() + " "):
            text = text[len(name) + 1:]
    return text


def parse(lines, skipped):
    names = cardholder_names(lines)
    rows = generic.parse(lines, skipped)
    for row in rows:
        row["description"] = clean_description(row["description"], names)
    return rows


def printed_total(lines, label):
    # the amount Amex prints next to a total, like "Total New Charges $0.00 $6,319.62 $6,319.62"
    for line in lines:
        line = " ".join(line.split())
        if line.lower().startswith(label):
            found = MONEY.findall(line)
            if found:
                return parse_amount(found[-1])  # last column is the total
    return None


def check_totals(lines, rows):
    charges = printed_total(lines, "total new charges")
    fees = printed_total(lines, "total fees for this period") or 0
    interest = printed_total(lines, "total interest charged for this period") or 0
    payments_and_credits = printed_total(lines, "total payments and credits")
    if charges is None or payments_and_credits is None:
        return None

    purchases = [row for row in rows if not row["payment"]]
    payments = [row for row in rows if row["payment"]]
    problems = []

    spent = round(sum(row["amount"] for row in purchases if row["amount"] > 0), 2)
    expected = round(charges + fees + interest, 2)
    if spent != expected:
        problems.append(f"Purchases add up to ${spent:,.2f} but the statement says ${expected:,.2f}.")

    credits = round(sum(row["amount"] for row in purchases if row["amount"] < 0), 2)
    expected = round(payments_and_credits - sum(row["amount"] for row in payments), 2)
    if credits != expected:
        problems.append(f"Credits add up to ${credits:,.2f} but the statement says ${expected:,.2f}.")
    return problems
