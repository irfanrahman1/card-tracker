"""Reads purchases from any bank's PDF statement.

Most statements print a purchase in one of two ways:

    10/17   SAMS HALAL CART   NEW YORK NY          8.48       <- all on one line

    09/20/26 ROYAL AIR MAROC  UNITED STATES                    <- date + description,
    Ticket Number: 1234                                           a few extra lines,
    $900.93                                                       then the amount alone

So we look for lines that start with a date. If the amount is at the end of
that line we're done; if not, we look a few lines down for a line that's just
an amount.
"""
import re

from ..csv_source import PAYMENT
from .text import AMOUNT, DATE, parse_amount, parse_date, statement_end_date

NAME = "generic"

# starts with a date, maybe a second date (posting date), maybe a * after a date
# e.g. "12/03  12/04  TRADER JOE'S ..." or "10/12/26* AUTOPAY ..."
DATE_LINE = re.compile(rf"^\s*({DATE})\*?\s+(?:{DATE}\*?\s+)?(.*[A-Za-z].*)$", re.IGNORECASE)

# description then an amount at the end. Some banks put a symbol after the amount (like ⧫)
# e.g. "TRADER JOE'S #552  NEW YORK NY     54.20"
WITH_AMOUNT = re.compile(rf"^(.*?[A-Za-z].*?)\s+({AMOUNT})\s*[^\w\s]*\s*$", re.IGNORECASE)

# a line that's only an amount, e.g. "$900.93" or "-$23.94 ⧫"
ONLY_AMOUNT = re.compile(rf"^\s*({AMOUNT})\s*[^\w\s]*\s*$", re.IGNORECASE)

LOOK_AHEAD = 12  # how many lines down we look for the amount

# summary lines on the statement that can look like purchases
SKIP_WORDS = [
    "balance", "minimum payment", "payment due", "credit limit", "available credit",
    "cash advance limit", "annual percentage", "closing date", "statement period",
    "statement date", "total fees", "total interest", "total purchases", "total payments",
    "total credits", "total for this period", "rewards earned",
]


def detects(text):
    return True  # it's the backup, so it takes anything


def find_amount_below(lines, start):
    """Look under line `start` for a line that's just an amount.
    Returns (amount text, line number) or (None, None)."""
    for j in range(start + 1, min(start + 1 + LOOK_AHEAD, len(lines))):
        if DATE_LINE.match(lines[j]):
            return None, None  # the next purchase started first
        match = ONLY_AMOUNT.match(lines[j])
        if match:
            return match.group(1), j
    return None, None


def parse(lines, skipped):
    end = statement_end_date(lines)
    rows = []
    i = 0
    while i < len(lines):
        match = DATE_LINE.match(lines[i])
        if not match:
            i += 1
            continue
        date_text, rest = match.groups()

        # is the amount on the same line?
        same_line = WITH_AMOUNT.match(rest)
        if same_line:
            description, amount_text = same_line.groups()
            last_line = i
        else:
            description = rest
            amount_text, last_line = find_amount_below(lines, i)
            if amount_text is None:
                i += 1
                continue

        description = " ".join(description.split())
        i = last_line + 1

        if any(word in description.lower() for word in SKIP_WORDS):
            continue
        try:
            date = parse_date(date_text, end)
            amount = parse_amount(amount_text)
        except ValueError as e:
            skipped.append(f"{description}: {e}")
            continue
        if amount == 0:
            continue

        # paying the card bill isn't spending, but we keep it (marked) for the totals check
        is_payment = bool(PAYMENT.search(description))
        if is_payment:
            skipped.append(description + ": card payment, not a purchase")
        rows.append({"date": date, "description": description, "amount": amount, "payment": is_payment})
    return rows


def balances(lines, label):
    """Every amount printed on a line with `label`, like 'Previous Balance $1,766.12'."""
    values = []
    for line in lines:
        text = " ".join(line.split())
        position = text.lower().find(label)
        if position == -1:
            continue
        found = re.findall(AMOUNT, text[position:], re.IGNORECASE)
        if found:
            values.append(parse_amount(found[-1]))
    return values


def check_totals(lines, rows):
    """Everything on a statement (purchases, refunds, payments, fees) adds up to
    how much the balance changed: new balance - previous balance.
    Returns None if the balances aren't printed in a way we can read,
    [] if it adds up, or a list with the problem."""
    previous = balances(lines, "previous balance")
    new = balances(lines, "new balance")
    if not previous or not new:
        return None

    change = round(sum(row["amount"] for row in rows), 2)
    # some statements print these more than once (like a summary box), so any match counts
    for p in previous:
        for n in new:
            if round(n - p, 2) == change:
                return []
    return [f"Everything we read adds up to ${change:,.2f}, but the balance changed by "
            f"${new[0] - previous[0]:,.2f}. Some purchases may be missing."]
