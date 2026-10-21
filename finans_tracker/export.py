"""CSV-export av transaktionsdata."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Optional

from finans_tracker.database import Database
from finans_tracker.models import TransactionType


class ExportError(Exception):
    """Fel vid export."""


def export_transactions_to_csv(
    db: Database,
    output_path: Path,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category_id: Optional[int] = None,
    transaction_type: Optional[TransactionType] = None,
) -> int:
    """
    Exporterar transaktioner till en CSV-fil.

    Args:
        db: Databasinstans.
        output_path: Målfil för exporten.
        date_from: Valfritt startdatum.
        date_to: Valfritt slutdatum.
        category_id: Valfri kategorifilter.
        transaction_type: Valfri typfilter.

    Returns:
        Antal exporterade rader.

    Raises:
        ExportError: Om exporten misslyckas.
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
                ["ID", "Datum", "Typ", "Belopp", "Kategori", "Beskrivning"]
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
        raise ExportError(f"Kunde inte skriva till fil: {output_path}") from exc

    return len(transactions)
