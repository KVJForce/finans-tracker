"""Tester för CSV-import, kategorisering och dubblettdetektering."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from finans_tracker.database import Database, DatabaseError
from finans_tracker.importers.bank_csv import (
    CsvImportError,
    detect_delimiter,
    parse_bank_csv,
)
from finans_tracker.importers.categorizer import suggest_category
from finans_tracker.importers.normalize import fold_text, parse_amount, parse_date
from finans_tracker.importers.service import build_transactions, load_import
from finans_tracker.models import Transaction, TransactionType


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1234,56", 1234.56),
        ("1 234,56", 1234.56),
        ("1 234,56 kr", 1234.56),
        ("1 234,56 SEK", 1234.56),
        ("-342,50", -342.50),
        ("\u2212342,50", -342.50),
        ("1.234,56", 1234.56),
        ("1,234.56", 1234.56),
        ("(1 234,56)", -1234.56),
        ("12,5", 12.5),
        ("1.234", 1234.0),
    ],
)
def test_parse_amount(raw: str, expected: float) -> None:
    assert parse_amount(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", "abc", "12,34,56 kr"])
def test_parse_amount_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_amount(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-09-01", date(2026, 9, 1)),
        ("20260901", date(2026, 9, 1)),
        ("2026/09/01", date(2026, 9, 1)),
        ("01/09/2026", date(2026, 9, 1)),
        ("2026-09-01 14:30", date(2026, 9, 1)),
    ],
)
def test_parse_date(raw: str, expected: date) -> None:
    assert parse_date(raw) == expected


def test_fold_text() -> None:
    assert fold_text("Hemköp  NÄRA") == "hemkop nara"


def test_detect_delimiter_with_decimal_commas() -> None:
    text = (
        "Datum;Beskrivning;Belopp\n"
        "2026-09-01;ICA NÄRA;1 234,56\n"
        "2026-09-02;SL BILJETT;-39,00\n"
    )
    assert detect_delimiter(text) == ";"


def test_parse_semicolon_file_with_preamble(tmp_path: Path) -> None:
    content = (
        "Kontoutdrag;2026-09-30\n"
        "Datum;Beskrivning;Belopp;Typ\n"
        "2026-09-01;Lön september;28500,00;Inkomst\n"
        "2026-09-02;ICA NÄRA;-342,50;Utgift\n"
        "2026-09-03;SL BILJETT;-39,00;\n"
        "2026-09-04;Okänd rad;;Utgift\n"
    )
    path = tmp_path / "bank.csv"
    path.write_text(content, encoding="utf-8")

    parsed = parse_bank_csv(path)

    assert len(parsed.transactions) == 3
    assert parsed.skipped_rows == 1
    assert parsed.delimiter == ";"
    assert parsed.transactions[0].transaction_type == TransactionType.INCOME
    assert parsed.transactions[0].amount == pytest.approx(28500.0)
    assert parsed.transactions[1].transaction_type == TransactionType.EXPENSE
    assert parsed.transactions[2].transaction_type == TransactionType.EXPENSE


def test_parse_comma_file_with_english_headers(tmp_path: Path) -> None:
    content = (
        "Date,Description,Amount,Type\n"
        "2026-09-01,Salary,28500.00,Income\n"
        '2026-09-02,"ICA; NARA",-342.50,Expense\n'
    )
    path = tmp_path / "bank.csv"
    path.write_text(content, encoding="utf-8")

    parsed = parse_bank_csv(path)

    assert parsed.delimiter == ","
    assert len(parsed.transactions) == 2
    assert parsed.transactions[1].description == "ICA; NARA"
    assert parsed.transactions[1].amount == pytest.approx(342.50)


def test_parse_cp1252_file(tmp_path: Path) -> None:
    content = (
        "Datum;Beskrivning;Belopp\n"
        "2026-09-01;Lön;28500,00\n"
        "2026-09-02;Hemköp;-342,50\n"
    )
    path = tmp_path / "bank.csv"
    path.write_bytes(content.encode("cp1252"))

    parsed = parse_bank_csv(path)

    assert parsed.encoding == "cp1252"
    assert parsed.transactions[0].description == "Lön"
    assert parsed.transactions[1].description == "Hemköp"


def test_parse_missing_columns_raises(tmp_path: Path) -> None:
    path = tmp_path / "bank.csv"
    path.write_text("Foo;Bar\n1;2\n", encoding="utf-8")

    with pytest.raises(CsvImportError):
        parse_bank_csv(path)


def test_parse_empty_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "bank.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(CsvImportError):
        parse_bank_csv(path)


@pytest.fixture
def database(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_suggest_category_uses_rules(database: Database) -> None:
    categories = database.get_categories()

    assert (
        suggest_category("ICA NÄRA STOCKHOLM", TransactionType.EXPENSE, categories)
        == "Mat & dryck"
    )
    assert (
        suggest_category("SL BILJETT", TransactionType.EXPENSE, categories)
        == "Transport"
    )
    assert (
        suggest_category("SPOTIFY AB", TransactionType.EXPENSE, categories)
        == "Underhållning"
    )
    assert (
        suggest_category("LÖN SEPTEMBER", TransactionType.INCOME, categories)
        == "Lön"
    )
    assert (
        suggest_category("Okänd butik", TransactionType.EXPENSE, categories)
        == "Övrigt"
    )
    assert (
        suggest_category("ICA NÄRA", TransactionType.INCOME, categories)
        == "Övrigt"
    )


def test_import_marks_duplicates_and_imports_new_rows(
    tmp_path: Path, database: Database
) -> None:
    mat = next(c for c in database.get_categories() if c.name == "Mat & dryck")
    existing = Transaction(
        id=None,
        amount=342.50,
        category_id=mat.id,
        transaction_date=date(2026, 9, 2),
        description="ICA NÄRA",
        transaction_type=TransactionType.EXPENSE,
    )
    database.add_transaction(existing)

    path = tmp_path / "bank.csv"
    path.write_text(
        "Datum;Beskrivning;Belopp;Typ\n"
        "2026-09-02;ICA NÄRA;-342,50;Utgift\n"
        "2026-09-02;ICA NÄRA;-342,50;Utgift\n"
        "2026-09-01;Lön;28500,00;Inkomst\n",
        encoding="utf-8",
    )

    preview = load_import(path, database)

    assert len(preview.transactions) == 3
    assert preview.duplicates == 1
    assert len(preview.importable) == 2
    assert preview.transactions[2].category_name == "Lön"

    transactions = build_transactions(preview)
    assert database.add_transactions(transactions) == 2

    second_preview = load_import(path, database)
    assert second_preview.duplicates == 3
    assert len(second_preview.importable) == 0


def test_bulk_insert_rolls_back_on_invalid_category(
    tmp_path: Path, database: Database
) -> None:
    transaction = Transaction(
        id=None,
        amount=10.0,
        category_id=9999,
        transaction_date=date(2026, 9, 1),
        description="Test",
        transaction_type=TransactionType.EXPENSE,
    )

    with pytest.raises(DatabaseError):
        database.add_transactions([transaction])

    assert database.get_transactions() == []
