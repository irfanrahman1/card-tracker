"""Purchases from an uploaded CSV file (a bank/card export or a hand-made sheet).

Column names are matched loosely (case-insensitive), so exports from Amex,
Chase, Capital One, Discover, Citi, Apple Card and Bank of America work as-is.
Required: a date, a merchant/description, and an amount (or Debit/Credit columns).
Optional: category, type, card (card name).

How amounts are read:
  - Card payments ("AUTOPAY PAYMENT - THANK YOU") are skipped: they aren't spending.
  - Refunds and statement credits are kept as negative amounts, so they subtract
    from their category (an Amazon refund lowers Shopping).
  - Banks disagree on the sign of purchases (Amex: +, Chase: -). We look at the
    whole file: whichever sign most rows have is treated as "purchase".
"""
import csv
import hashlib
import io
import re
from datetime import date, datetime

from ..schemas import TransactionIn
from .base import TransactionSource

# Header names we accept for each field, in order of preference.
COLUMNS = {
    "date": ["date", "transaction date", "trans. date", "trans date", "posted date", "post date", "posting date"],
    "merchant": ["merchant", "description", "payee", "name", "original description"],
    "amount": ["amount", "amount (usd)", "transaction amount"],
    "debit": ["debit", "debit amount", "charge"],
    "credit": ["credit", "credit amount"],
    "category": ["category"],
    "type": ["type", "transaction type"],
    "card": ["card", "card name"],
}

DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d-%b-%Y", "%b %d, %Y", "%Y/%m/%d"]

# Rows that are paying the card bill, not buying something.
PAYMENT = re.compile(
    r"payment.*thank|thank you.*payment|autopay|auto pay|online payment|mobile payment|"
    r"payment received|ach pmt|epayment|directpay|payment/credit|payments and credits",
    re.IGNORECASE,
)
REFUND_TYPES = {"return", "refund", "credit", "adjustment"}
PURCHASE_TYPES = {"sale", "purchase", "debit"}


def _parse_date(text: str) -> date:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognized date '{text}'")


def _parse_number(text: str) -> float | None:
    """'$1,234.56' -> 1234.56, '(12.00)' -> -12.0, '' -> None."""
    cleaned = (text or "").strip().replace("$", "").replace(",", "")
    if not cleaned:
        return None
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        return float(cleaned)
    except ValueError:
        raise ValueError(f"unrecognized amount '{text}'")


def _split_amex(description: str) -> tuple[str, str]:
    """Amex pads descriptions into fixed-width columns: 20 chars of merchant, then city/state.

    'AplPay SAMS HALAL CANew York            NY' -> ('AplPay SAMS HALAL CA', 'New York NY')
    Short, unpadded ones like 'UBER' or 'Platinum Uber One Credit' are left whole.
    """
    if len(description) > 20 and ("  " in description or len(description) >= 40):
        return description[:20].strip(), " ".join(description[20:].split())
    return description.strip(), ""


class CSVSource(TransactionSource):
    name = "csv"

    def __init__(self, content: bytes, card_ids_by_name: dict[str, int], default_card_id: int | None = None):
        # utf-8-sig strips the invisible marker Excel puts at the start of CSVs.
        self.text = content.decode("utf-8-sig", errors="replace")
        self.card_ids_by_name = {k.lower(): v for k, v in card_ids_by_name.items()}
        self.default_card_id = default_card_id
        # Filled in by fetch(): rows we didn't import, with the reason.
        self.skipped: list[str] = []

    def _find_columns(self, headers: list[str]) -> dict[str, str]:
        """Map our field names to the file's actual header names."""
        lowered = {h.strip().lower(): h for h in headers if h}
        found = {}
        for field, options in COLUMNS.items():
            for option in options:
                if option in lowered and lowered[option] not in found.values():
                    found[field] = lowered[option]
                    break
        return found

    def _rows(self):
        """Yield (line_number, row_dict, columns). Skips any intro lines above the header."""
        lines = self.text.splitlines()
        # Some exports put a title or account info above the real header row.
        start = next(
            (i for i, line in enumerate(lines[:15])
             if "date" in line.lower() and re.search(r"amount|debit|credit", line, re.IGNORECASE)),
            0,
        )
        reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
        cols = self._find_columns(reader.fieldnames or [])
        has_amount = "amount" in cols or "debit" in cols
        missing = [f for f, ok in (("date", "date" in cols), ("merchant", "merchant" in cols), ("amount", has_amount)) if not ok]
        if missing:
            raise ValueError(f"CSV is missing column(s): {', '.join(missing)}")
        amex = "card member" in {h.strip().lower() for h in reader.fieldnames or []}
        for offset, row in enumerate(reader):
            yield start + offset + 2, row, cols, amex  # +2: header line, 1-based numbering

    def fetch(self) -> list[TransactionIn]:
        # First pass: read every row into plain values.
        parsed = []
        for line_no, row, cols, amex in self._rows():
            get = lambda field: (row.get(cols[field]) or "").strip() if field in cols else ""
            raw = get("merchant")
            merchant, location = _split_amex(raw) if amex else (raw, "")
            label = get("category")
            kind = get("type").lower()
            try:
                if not raw:
                    raise ValueError("no merchant/description")
                if PAYMENT.search(raw) or PAYMENT.search(label) or kind == "payment":
                    self.skipped.append(f"line {line_no}: card payment, not a purchase")
                    continue
                when = _parse_date(get("date"))
                if "amount" in cols:
                    value, signed = _parse_number(get("amount")), False
                else:  # separate Debit/Credit columns: debit = purchase, credit = refund
                    debit, credit = _parse_number(get("debit")), _parse_number(get("credit"))
                    value, signed = (abs(debit), True) if debit else (-abs(credit or 0), True)
                if not value:
                    raise ValueError("empty or zero amount")
            except ValueError as err:
                self.skipped.append(f"line {line_no}: {err}")
                continue
            parsed.append((line_no, when, raw, merchant, location, value, signed, label, kind, get("card")))

        # Which sign means "purchase" in this file? Rows typed "Sale"/"Purchase" settle it
        # (Chase, Apple Card); otherwise whichever sign most rows use.
        unsigned = [p for p in parsed if not p[6]]
        typed = [p[5] for p in unsigned if p[8] in PURCHASE_TYPES]
        values = typed or [p[5] for p in unsigned]
        purchases_negative = sum(v < 0 for v in values) > sum(v > 0 for v in values)

        results = []
        seen: dict[str, int] = {}  # counts identical rows so real repeats aren't dropped
        for line_no, when, raw, merchant, location, value, signed, label, kind, card in parsed:
            amount = value if signed else (-value if purchases_negative else value)
            if kind in REFUND_TYPES and amount > 0:
                amount = -amount

            # A stable id from the row's contents, so uploading the same file (or an
            # overlapping export) twice doesn't create duplicates.
            key = f"{when}|{raw.lower()}|{amount:.2f}"
            seen[key] = seen.get(key, 0) + 1
            external_id = hashlib.sha1(f"{key}|{seen[key]}".encode()).hexdigest()[:16]

            results.append(TransactionIn(
                date=when,
                merchant=merchant,
                description=location,
                amount=amount,
                category=label or None,
                card_id=self.card_ids_by_name.get(card.lower(), self.default_card_id),
                external_id=external_id,
            ))
        return results
