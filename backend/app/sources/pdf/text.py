"""Getting text out of a PDF, and the small reading helpers every parser shares."""
import io
import re
from datetime import date, datetime, timedelta

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"

# Dates as statements print them: 10/17, 10/17/26, 10/17/2026, Oct 17, Oct 17, 2026.
DATE = rf"(?:\d{{1,2}}/\d{{1,2}}(?:/\d{{2}}(?:\d{{2}})?)?|(?:{MONTHS})[a-z]*\.? \d{{1,2}}(?:, ?\d{{4}})?)"
# Money with cents: 8.48, $1,234.56, -$23.94, ($23.94), 23.94 CR, 23.94-
AMOUNT = r"(?:[-−–]\s?)?\(?\$?\s?\d{1,3}(?:,\d{3})*\.\d{2}\)?(?:\s?CR|-)?"

_FULL_DATE = re.compile(
    rf"\b(\d{{1,2}}/\d{{1,2}}/\d{{4}}|\d{{1,2}}/\d{{1,2}}/\d{{2}}|(?:{MONTHS})[a-z]*\.? \d{{1,2}}, ?\d{{4}})\b",
    re.IGNORECASE,
)
# PDF fonts often print ' and " as curly quotes. Straighten them so merchant names
# match the keywords in categories.py ("trader joe's") and your saved rules.
_STRAIGHTEN = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})

_END_HINT = re.compile(r"closing date|statement date|statement period|billing period|period ending", re.IGNORECASE)


def _page_text(page) -> str:
    """Text of one page. "layout" mode keeps things that sit side by side on the page
    (date, merchant, amount) on one line. Some PDFs (like Amex's regular statement)
    come out blank in layout mode, so we fall back to plain mode for those pages."""
    text = page.extract_text(extraction_mode="layout") or ""
    if not text.strip():
        text = page.extract_text() or ""
    return text


def extract_lines(content: bytes, max_pages: int = 50) -> list[str]:
    """All non-empty lines of text in the PDF, top to bottom, page by page."""
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("This PDF is password-protected. Save an unlocked copy and try again.")
        if len(reader.pages) > max_pages:
            raise ValueError(f"This PDF has more than {max_pages} pages; that doesn't look like a statement.")
        pages = [_page_text(page) for page in reader.pages]
    except (PdfReadError, KeyError, TypeError, AttributeError) as err:
        raise ValueError("Couldn't read this file as a PDF.") from err
    lines = [line.rstrip().translate(_STRAIGHTEN) for page in pages for line in page.splitlines() if line.strip()]
    if not lines:
        raise ValueError("This PDF has no text in it (it may be a scanned image), so it can't be read.")
    return lines


def parse_amount(text: str) -> float:
    """'$1,234.56' -> 1234.56; '-$5.00', '($5.00)', '5.00 CR', '5.00-' -> -5.0."""
    cleaned = text.strip().replace("$", "").replace(",", "").replace(" ", "")
    negative = False
    for mark in ("−", "–", "-"):
        if cleaned.startswith(mark):
            negative, cleaned = True, cleaned[len(mark):]
    if cleaned.upper().endswith("CR"):
        negative, cleaned = True, cleaned[:-2]
    if cleaned.endswith("-"):
        negative, cleaned = True, cleaned[:-1]
    if cleaned.startswith("(") and cleaned.endswith(")"):
        negative, cleaned = True, cleaned[1:-1]
    value = float(cleaned)
    return -value if negative else value


def _to_date(text: str) -> date | None:
    text = " ".join(text.replace(".", "").split())
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%b %d, %Y", "%b %d,%Y", "%B %d, %Y", "%B %d,%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def statement_end_date(lines: list[str]) -> date | None:
    """The statement's closing date, used to work out the year of dates like '10/17'.

    Prefers a date on a line that says "closing date" / "statement period"; otherwise
    the latest full date anywhere in the statement.
    """
    hinted, everywhere = [], []
    for line in lines:
        found = [d for d in (_to_date(m) for m in _FULL_DATE.findall(line)) if d]
        everywhere += found
        if found and _END_HINT.search(line):
            hinted.append(max(found))
    candidates = hinted or everywhere
    return max(candidates) if candidates else None


def parse_date(text: str, end: date | None) -> date:
    """Read a statement date. A date with no year gets the year that puts it on or
    before the closing date (so 12/28 on a January statement is last year's)."""
    full = _to_date(text)
    if full:
        return full
    text = " ".join(text.replace(".", "").split())
    for fmt in ("%m/%d", "%b %d", "%B %d"):
        try:
            # Parse with a leap year so "02/29" works, then put the real year on.
            partial = datetime.strptime(f"2000 {text}", f"%Y {fmt}").date()
            break
        except ValueError:
            partial = None
    if partial is None:
        raise ValueError(f"unrecognized date '{text}'")
    end = end or date.today()
    for year in (end.year, end.year - 1):
        try:
            candidate = partial.replace(year=year)
        except ValueError:  # Feb 29 in a non-leap year
            continue
        if candidate <= end + timedelta(days=7):
            return candidate
    raise ValueError(f"unrecognized date '{text}'")
