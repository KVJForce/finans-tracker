"""Tolkning av CSV-exporter från svenska och utländska banker."""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from finans_tracker.importers.normalize import (
    clean_description,
    fold_text,
    parse_amount,
    parse_date,
)
from finans_tracker.models import TransactionType


class CsvImportError(Exception):
    """Fel som kan visas för användaren vid CSV-import."""


@dataclass
class ParsedTransaction:
    """En transaktion som tagits fram från en CSV-fil men ännu inte sparats."""

    transaction_date: date
    description: str
    amount: float
    transaction_type: TransactionType
    category_name: Optional[str] = None
    is_duplicate: bool = False


@dataclass
class ParsedFile:
    """Resultatet av att tolka en CSV-fil."""

    transactions: list[ParsedTransaction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped_rows: int = 0
    encoding: str = "utf-8"
    delimiter: str = ";"


HEADER_ALIASES: dict[str, set[str]] = {
    "date": {
        "datum",
        "date",
        "transaktionsdatum",
        "bokforingsdatum",
        "bokforingsdag",
        "value date",
    },
    "description": {
        "beskrivning",
        "text",
        "meddelande",
        "mottagare",
        "betalningsmottagare",
        "transaktionstext",
        "detaljer",
        "name",
        "description",
        "referens",
    },
    "amount": {
        "belopp",
        "amount",
        "summa",
        "belopp sek",
        "amount sek",
        "belopp i sek",
        "transaktionsbelopp",
        "value",
    },
    "type": {
        "typ",
        "type",
        "transaktionstyp",
        "debit kredit",
        "debit credit",
    },
    "category": {"kategori", "category"},
}

INCOME_TYPES = {
    "inkomst",
    "kredit",
    "credit",
    "in",
    "insattning",
    "deposit",
}
EXPENSE_TYPES = {
    "utgift",
    "debit",
    "deb",
    "out",
    "uttag",
    "withdrawal",
    "betalning",
}
TOTAL_WORDS = {"summa", "totalt", "total", "ingående saldo", "utgående saldo"}

MAX_WARNINGS = 20


def decode_csv(raw: bytes) -> tuple[str, str]:
    """
    Avkodar CSV-data med stöd för vanliga bankkodningar.

    Args:
        raw: Filens råa bytes.

    Returns:
        Tuple med (text, kodning).
    """
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"

    for encoding in ("utf-8", "cp1252"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    return raw.decode("latin-1"), "latin-1"


def detect_delimiter(text: str) -> str:
    """
    Hittar filens separator genom att välja den som ger mest konsekventa rader.

    Decimalskommatecken i svenska belopp gör att en enkel räkning av tecken
    inte räcker. Därför jämförs antalet kolumner per rad för varje kandidat.

    Args:
        text: Filens innehåll som text.

    Returns:
        Separatorn, normalt ";" eller ",".
    """
    sample = "\n".join(text.splitlines()[:30])
    best: Optional[tuple[str, tuple[int, int]]] = None

    for delimiter in (";", ",", "\t", "|"):
        try:
            rows = list(csv.reader(io.StringIO(sample), delimiter=delimiter))
        except csv.Error:
            continue

        counts = [len(row) for row in rows if row and any(cell.strip() for cell in row)]
        if not counts:
            continue

        column_count, frequency = Counter(counts).most_common(1)[0]
        if column_count < 2:
            continue

        score = (frequency, column_count)
        if best is None or score > best[1]:
            best = (delimiter, score)

    return best[0] if best else ";"


def _header_key(value: str) -> str:
    """Normaliserar en kolumnrubrik för jämförelse."""
    return re.sub(r"[^a-z0-9]+", " ", fold_text(value)).strip()


def _find_header(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    """Hittar rubrikraden och mappar kolumnnamn till kolumnindex."""
    best: Optional[tuple[int, dict[str, int]]] = None

    for index, row in enumerate(rows[:20]):
        mapping: dict[str, int] = {}
        for column, cell in enumerate(row):
            key = _header_key(cell)
            for field_name, aliases in HEADER_ALIASES.items():
                if field_name not in mapping and key in aliases:
                    mapping[field_name] = column
                    break

        if best is None or len(mapping) > len(best[1]):
            best = (index, mapping)

    if best is None or not {"date", "description", "amount"} <= best[1].keys():
        raise CsvImportError(
            "Kunde inte hitta kolumnerna datum, beskrivning och belopp. "
            "Kontrollera att filen är en CSV-export från din bank."
        )

    return best


def _parse_type(value: str) -> Optional[TransactionType]:
    """Tolkar en typkolumn som inkomst eller utgift."""
    key = _header_key(value)
    if key in INCOME_TYPES:
        return TransactionType.INCOME
    if key in EXPENSE_TYPES:
        return TransactionType.EXPENSE
    return None


def _cell(row: list[str], index: Optional[int]) -> str:
    """Hämtar en cell ur en rad och tål att raden är kortare än rubriken."""
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def _add_warning(parsed: ParsedFile, message: str) -> None:
    """Sparar ett begränsat antal varningar."""
    if len(parsed.warnings) < MAX_WARNINGS:
        parsed.warnings.append(message)


def parse_bank_csv(path: Path) -> ParsedFile:
    """
    Läser och tolkar en CSV-export från en bank.

    Filen får innehålla inledande rader före rubrikraden. Både
    semikolon- och kommaavgränsade filer stöds, liksom UTF-8 och CP1252.

    Args:
        path: Sökväg till CSV-filen.

    Returns:
        ParsedFile med giltiga transaktioner och eventuella varningar.

    Raises:
        CsvImportError: Om filen inte kan läsas eller saknar rätt kolumner.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CsvImportError(f"Kunde inte läsa filen: {path}") from exc

    if not raw.strip():
        raise CsvImportError("Filen är tom.")

    text, encoding = decode_csv(raw)
    delimiter = detect_delimiter(text)

    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    except csv.Error as exc:
        raise CsvImportError("Kunde inte tolka filen som CSV.") from exc

    header_index, columns = _find_header(rows)
    parsed = ParsedFile(encoding=encoding, delimiter=delimiter)

    for line_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not row or not any(cell.strip() for cell in row):
            continue

        raw_date = _cell(row, columns.get("date"))
        raw_description = _cell(row, columns.get("description"))
        raw_amount = _cell(row, columns.get("amount"))

        description = clean_description(raw_description)
        folded_description = fold_text(description)

        if not raw_date and any(word in folded_description for word in TOTAL_WORDS):
            continue

        if not raw_date:
            parsed.skipped_rows += 1
            _add_warning(parsed, f"Rad {line_number}: datum saknas.")
            continue

        try:
            transaction_date = parse_date(raw_date)
        except ValueError:
            parsed.skipped_rows += 1
            _add_warning(parsed, f"Rad {line_number}: ogiltigt datum {raw_date!r}.")
            continue

        try:
            amount = parse_amount(raw_amount)
        except ValueError:
            parsed.skipped_rows += 1
            _add_warning(parsed, f"Rad {line_number}: ogiltigt belopp {raw_amount!r}.")
            continue

        if amount == 0:
            parsed.skipped_rows += 1
            _add_warning(parsed, f"Rad {line_number}: beloppet är noll.")
            continue

        transaction_type = _parse_type(_cell(row, columns.get("type")))
        if transaction_type is None:
            transaction_type = (
                TransactionType.EXPENSE if amount < 0 else TransactionType.INCOME
            )

        parsed.transactions.append(
            ParsedTransaction(
                transaction_date=transaction_date,
                description=description or "Importerad transaktion",
                amount=abs(amount),
                transaction_type=transaction_type,
                category_name=_cell(row, columns.get("category")) or None,
            )
        )

    if not parsed.transactions:
        raise CsvImportError(
            "Inga giltiga transaktioner hittades i filen. "
            "Kontrollera datum- och beloppsformaten."
        )

    return parsed
