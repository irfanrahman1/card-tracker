"""Import purchases from a PDF credit card statement."""
import hashlib

from ...schemas import TransactionIn
from ..base import TransactionSource
from . import amex, generic
from .text import extract_lines

# Bank parsers go in this list. Each one is a file in this folder with:
#   NAME, detects(text) -> True if it's that bank's statement, parse(lines, skipped) -> rows
# and optionally check_totals(lines, rows). If none of them match, we use generic.py,
# which works for most banks. Only add a bank here if generic.py gets its statements wrong.
BANK_PARSERS = [amex]


def pick_parser(text, parsers=None):
    if parsers is None:
        parsers = BANK_PARSERS
    for parser in parsers:
        if parser.detects(text):
            return parser
    return generic


class PDFSource(TransactionSource):
    name = "pdf"

    def __init__(self, content, default_card_id=None, parsers=None, leave_out=None):
        self.content = content
        self.default_card_id = default_card_id
        self.parsers = parsers
        self.leave_out = leave_out or set()  # ids of rows the user unticked on the review screen
        self.parser_name = ""
        self.skipped = []
        self.warnings = []  # problems found by the totals check
        self.totals_checked = False  # True if we could compare with the statement's own totals

    def fetch(self):
        lines = extract_lines(self.content)
        parser = pick_parser("\n".join(lines), self.parsers)
        self.parser_name = parser.NAME
        rows = parser.parse(lines, self.skipped)

        # double-check against the totals printed on the statement, if the parser can
        if hasattr(parser, "check_totals"):
            result = parser.check_totals(lines, rows)
            if result is not None:
                self.totals_checked = True
                self.warnings = result

        # card payments were only kept for the totals check, they aren't purchases
        purchases = [row for row in rows if not row.get("payment")]
        if len(purchases) == 0:
            raise ValueError("Couldn't find any purchases in this PDF. If your bank has a CSV download, try that instead.")

        results = []
        counts = {}
        for row in purchases:
            # id made from the row itself, so uploading the same PDF twice doesn't add duplicates
            # (counts is there so two real identical purchases on the same day both get saved)
            key = f"{row['date']}|{row['description'].lower()}|{row['amount']:.2f}"
            counts[key] = counts.get(key, 0) + 1
            external_id = hashlib.sha1(f"{key}|{counts[key]}".encode()).hexdigest()[:16]
            if external_id in self.leave_out:
                continue

            results.append(TransactionIn(
                date=row["date"],
                merchant=row["description"],
                amount=row["amount"],
                card_id=self.default_card_id,
                external_id=external_id,
            ))
        return results
