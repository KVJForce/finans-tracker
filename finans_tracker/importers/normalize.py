"""Normalisering av belopp, datum och text vid CSV-import."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Optional

_CURRENCY_RE = re.compile(r"(kr|sek|:-)", re.IGNORECASE)

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y%m%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
)


def _grouped_integer(text: str, separator: str) -> Optional[str]:
    """Tar bort tusentalsavgränsare om grupperna är tre siffror vardera."""
    parts = text.split(separator)
    if len(parts) < 2 or not parts[0].isdigit():
        return None
    if all(len(part) == 3 and part.isdigit() for part in parts[1:]):
        return "".join(parts)
    return None


def parse_amount(raw: str) -> float:
    """
    Tolkar ett belopp från en bank-CSV.

    Stödjer svenska och engelska format, till exempel "1 234,56",
    "-1.234,56", "1,234.56" och "(1 234,56)".

    Args:
        raw: Beloppet som text.

    Returns:
        Beloppet som flyttal. Negativa belopp behåller sitt tecken.

    Raises:
        ValueError: Om beloppet inte kan tolkas.
    """
    text = raw.strip().replace("\u00a0", " ").replace("\u2212", "-")
    if not text:
        raise ValueError("tomt belopp")

    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]

    text = _CURRENCY_RE.sub("", text).replace(" ", "").replace("'", "")

    if text.endswith("-"):
        negative = not negative
        text = text[:-1]
    if text.startswith("-"):
        negative = not negative
        text = text[1:]
    if text.startswith("+"):
        text = text[1:]

    if not text:
        raise ValueError(f"ogiltigt belopp: {raw!r}")

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        head, _, tail = text.rpartition(",")
        if text.count(",") == 1 and head and len(tail) in (1, 2):
            text = f"{head}.{tail}"
        else:
            grouped = _grouped_integer(text, ",")
            if grouped is None:
                raise ValueError(f"ogiltigt belopp: {raw!r}")
            text = grouped
    elif "." in text:
        head, _, tail = text.rpartition(".")
        if text.count(".") == 1 and head and len(tail) in (1, 2):
            text = f"{head}.{tail}"
        else:
            grouped = _grouped_integer(text, ".")
            if grouped is None:
                raise ValueError(f"ogiltigt belopp: {raw!r}")
            text = grouped

    try:
        value = float(text)
    except ValueError as exc:
        raise ValueError(f"ogiltigt belopp: {raw!r}") from exc

    return -value if negative else value


def parse_date(raw: str) -> date:
    """
    Tolkar ett datum från en bank-CSV.

    Args:
        raw: Datumet som text.

    Returns:
        Datumet.

    Raises:
        ValueError: Om datumet inte matchar något känt format.
    """
    text = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"ogiltigt datum: {raw!r}")


def clean_description(raw: str) -> str:
    """Tar bort extra blanksteg och radbrytningar från en beskrivning."""
    return " ".join(raw.split())


def fold_text(value: str) -> str:
    """
    Normaliserar text för sökning: gemener och utan diakriter.

    Exempel: "Hemköp" blir "hemkop".
    """
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return " ".join(without_marks.casefold().split())
