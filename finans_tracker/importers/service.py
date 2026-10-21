"""Orchestration of CSV import: parsing, duplicates, and categories."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from finans_tracker.database import Database
from finans_tracker.importers.bank_csv import (
    CsvImportError,
    ParsedTransaction,
    parse_bank_csv,
)
from finans_tracker.importers.categorizer import suggest_category
from finans_tracker.models import (
    Category,
    CategoryType,
    Transaction,
    TransactionType,
    transaction_fingerprint,
)


@dataclass
class ImportPreview:
    """Preview of a CSV import."""

    source: Path
    transactions: list[ParsedTransaction] = field(default_factory=list)
    categories: list[Category] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped_rows: int = 0
    encoding: str = "utf-8"
    delimiter: str = ";"

    @property
    def duplicates(self) -> int:
        """Number of rows that already exist in the database."""
        return sum(1 for transaction in self.transactions if transaction.is_duplicate)

    @property
    def importable(self) -> list[ParsedTransaction]:
        """Rows that will be imported."""
        return [
            transaction
            for transaction in self.transactions
            if not transaction.is_duplicate
        ]


def _is_compatible(category: Category, transaction_type: TransactionType) -> bool:
    """Checks that a category can be used for a transaction type."""
    if category.category_type == CategoryType.BOTH:
        return True
    if transaction_type == TransactionType.INCOME:
        return category.category_type == CategoryType.INCOME
    return category.category_type == CategoryType.EXPENSE


def _pick_category(
    transaction: ParsedTransaction, categories: list[Category]
) -> Optional[Category]:
    """Picks a valid category, falling back to "Other" as a last resort."""
    compatible = [
        category
        for category in categories
        if _is_compatible(category, transaction.transaction_type)
    ]
    for category in compatible:
        if category.name == transaction.category_name:
            return category
    for category in compatible:
        if category.name == "Other":
            return category
    return compatible[0] if compatible else None


def load_import(path: Path, db: Database) -> ImportPreview:
    """
    Reads a CSV file and prepares an import.

    Duplicates are identified by date, amount, type, and normalized
    description. If the file contains two identical rows and the database
    already has one of them, the other row is imported.

    Args:
        path: Path to the CSV file.
        db: Database to read existing transactions from.

    Returns:
        ImportPreview ready to be displayed and imported.

    Raises:
        CsvImportError: If the file cannot be parsed.
    """
    parsed = parse_bank_csv(path)
    categories = db.get_categories()

    dates = [transaction.transaction_date for transaction in parsed.transactions]
    existing = db.get_transactions(date_from=min(dates), date_to=max(dates))
    existing_counts = Counter(
        transaction_fingerprint(
            transaction.transaction_date,
            transaction.amount,
            transaction.transaction_type,
            transaction.description,
        )
        for transaction in existing
    )

    for transaction in parsed.transactions:
        fingerprint = transaction_fingerprint(
            transaction.transaction_date,
            transaction.amount,
            transaction.transaction_type,
            transaction.description,
        )
        if existing_counts[fingerprint] > 0:
            transaction.is_duplicate = True
            existing_counts[fingerprint] -= 1

    for transaction in parsed.transactions:
        category = _pick_category(transaction, categories)
        if category is None:
            transaction.category_name = None
            continue
        if category.name != transaction.category_name:
            suggestion = suggest_category(
                transaction.description, transaction.transaction_type, categories
            )
            transaction.category_name = suggestion or category.name

    return ImportPreview(
        source=path,
        transactions=parsed.transactions,
        categories=categories,
        warnings=parsed.warnings,
        skipped_rows=parsed.skipped_rows,
        encoding=parsed.encoding,
        delimiter=parsed.delimiter,
    )


def build_transactions(preview: ImportPreview) -> list[Transaction]:
    """
    Converts importable rows into Transaction objects.

    Args:
        preview: The preview to import.

    Returns:
        Transactions ready to be saved.

    Raises:
        CsvImportError: If a row lacks a valid category.
    """
    by_name = {category.name: category for category in preview.categories}
    result: list[Transaction] = []

    for item in preview.importable:
        category = by_name.get(item.category_name or "")
        if category is None or category.id is None:
            raise CsvImportError(
                f"No valid category for '{item.description}'."
            )

        result.append(
            Transaction(
                id=None,
                amount=item.amount,
                category_id=category.id,
                transaction_date=item.transaction_date,
                description=item.description,
                transaction_type=item.transaction_type,
            )
        )

    return result
