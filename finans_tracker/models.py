"""Datamodeller för Finans Tracker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


def normalize_description(description: str) -> str:
    """Normaliserar en beskrivning för jämförelse och kategorisering."""
    return " ".join(description.casefold().split())


def transaction_fingerprint(
    transaction_date: date,
    amount: float,
    transaction_type: "TransactionType",
    description: str,
) -> tuple[str, int, str, str]:
    """
    Skapar ett fingeravtryck som identifierar en transaktion.

    Används för att hitta dubbletter vid import. Beloppet räknas om till
    ören för att undvika flyttalsproblem.

    Returns:
        Tuple med (datum, belopp i ören, typ, normaliserad beskrivning).
    """
    return (
        transaction_date.isoformat(),
        round(abs(amount) * 100),
        transaction_type.value,
        normalize_description(description),
    )


class TransactionType(str, Enum):
    """Typ av transaktion."""

    INCOME = "income"
    EXPENSE = "expense"


class CategoryType(str, Enum):
    """Typ av kategori."""

    INCOME = "income"
    EXPENSE = "expense"
    BOTH = "both"


@dataclass
class Category:
    """Representerar en transaktionskategori."""

    id: Optional[int]
    name: str
    color: str
    category_type: CategoryType

    @property
    def display_type(self) -> str:
        """Returnerar en läsbar typbeskrivning."""
        labels = {
            CategoryType.INCOME: "Inkomst",
            CategoryType.EXPENSE: "Utgift",
            CategoryType.BOTH: "Båda",
        }
        return labels[self.category_type]


@dataclass
class Transaction:
    """Representerar en finansiell transaktion."""

    id: Optional[int]
    amount: float
    category_id: int
    transaction_date: date
    description: str
    transaction_type: TransactionType
    category_name: Optional[str] = None
    category_color: Optional[str] = None

    @property
    def signed_amount(self) -> float:
        """Returnerar beloppet med rätt tecken."""
        if self.transaction_type == TransactionType.EXPENSE:
            return -abs(self.amount)
        return abs(self.amount)

    @property
    def display_type(self) -> str:
        """Returnerar en läsbar typbeskrivning."""
        return "Inkomst" if self.transaction_type == TransactionType.INCOME else "Utgift"


@dataclass
class MonthlySummary:
    """Sammanfattning av månadens ekonomi."""

    total_balance: float
    monthly_income: float
    monthly_expense: float
    transaction_count: int
