"""Import purchases from a PDF credit card statement."""
import hashlib

from ...schemas import TransactionIn
from ..base import TransactionSource
from . import generic
from .text import extract_lines

# Bank parsers go in this list. Each one is a file in this folder with:
#   NAME, detects(text) -> True if it's that bank's statement, parse(lines, skipped) -> rows
# If none of them match, we use generic.py
BANK_PARSERS = []


def pick_parser(text, parsers=None):
    if parsers is None:
        parsers = BANK_PARSERS
    for parser in parsers:
        if parser.detects(text):
            return parser
    return generic


class PDFSource(TransactionSource):
    name = "pdf"

    def __init__(self, content, default_card_id=None, parsers=None):
        self.content = content
        self.default_card_id = default_card_id
        self.parsers = parsers
        self.parser_name = ""
        self.skipped = []

    def fetch(self):
        lines = extract_lines(self.content)
        parser = pick_parser("\n".join(lines), self.parsers)
        self.parser_name = parser.NAME
        rows = parser.parse(lines, self.skipped)
        if len(rows) == 0:
            raise ValueError("Couldn't find any purchases in this PDF. If your bank has a CSV download, try that instead.")

        results = []
        counts = {}
        for row in rows:
            # id made from the row itself, so uploading the same PDF twice doesn't add duplicates
            # (counts is there so two real identical purchases on the same day both get saved)
            key = f"{row['date']}|{row['description'].lower()}|{row['amount']:.2f}"
            counts[key] = counts.get(key, 0) + 1
            external_id = hashlib.sha1(f"{key}|{counts[key]}".encode()).hexdigest()[:16]

            results.append(TransactionIn(
                date=row["date"],
                merchant=row["description"],
                amount=row["amount"],
                card_id=self.default_card_id,
                external_id=external_id,
            ))
        return results
