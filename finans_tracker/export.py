"""CSV export of transaction data."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Optional

from finans_tracker.database import Database
from finans_tracker.models import TransactionType


class ExportError(Exception):
    """Error during export."""


def export_transactions_to_csv(
    db: Database,
    output_path: Path,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category_id: Optional[int] = None,
    transaction_type: Optional[TransactionType] = None,
) -> int:
    """
    Exports transactions to a CSV file.

    Args:
        db: Database instance.
        output_path: Destination file for the export.
        date_from: Optional start date.
        date_to: Optional end date.
        category_id: Optional category filter.
        transaction_type: Optional type filter.

    Returns:
        Number of exported rows.

    Raises:
        ExportError: If the export fails.
    """
    transactions = db.get_transactions(
        date_from=date_from,
        date_to=date_to,
        category_id=category_id,
        transaction_type=transaction_type,
    )

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.writer(csvfile, delimiter=";")
            writer.writerow(
                ["ID", "Date", "Type", "Amount", "Category", "Description"]
            )
            for tx in transactions:
                writer.writerow(
                    [
                        tx.id,
                        tx.transaction_date.isoformat(),
                        tx.display_type,
                        f"{tx.amount:.2f}",
                        tx.category_name or "",
                        tx.description,
                    ]
                )
    except OSError as exc:
        raise ExportError(f"Could not write to file: {output_path}") from exc

    return len(transactions)
