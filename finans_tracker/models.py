"""Data models for Finance Tracker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


def normalize_description(description: str) -> str:
    """Normalizes a description for comparison and categorization."""
    return " ".join(description.casefold().split())


def transaction_fingerprint(
    transaction_date: date,
    amount: float,
    transaction_type: "TransactionType",
    description: str,
) -> tuple[str, int, str, str]:
    """
    Creates a fingerprint that identifies a transaction.

    Used to detect duplicates during import. The amount is converted to
    integer öre to avoid floating point issues.

    Returns:
        Tuple of (date, amount in öre, type, normalized description).
    """
    return (
        transaction_date.isoformat(),
        round(abs(amount) * 100),
        transaction_type.value,
        normalize_description(description),
    )


class TransactionType(str, Enum):
    """Type of transaction."""

    INCOME = "income"
    EXPENSE = "expense"


class CategoryType(str, Enum):
    """Type of category."""

    INCOME = "income"
    EXPENSE = "expense"
    BOTH = "both"


@dataclass
class Category:
    """Represents a transaction category."""

    id: Optional[int]
    name: str
    color: str
    category_type: CategoryType

    @property
    def display_type(self) -> str:
        """Returns a human-readable type label."""
        labels = {
            CategoryType.INCOME: "Income",
            CategoryType.EXPENSE: "Expense",
            CategoryType.BOTH: "Both",
        }
        return labels[self.category_type]


@dataclass
class Transaction:
    """Represents a financial transaction."""

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
        """Returns the amount with the correct sign."""
        if self.transaction_type == TransactionType.EXPENSE:
            return -abs(self.amount)
        return abs(self.amount)

    @property
    def display_type(self) -> str:
        """Returns a human-readable type label."""
        return "Income" if self.transaction_type == TransactionType.INCOME else "Expense"


@dataclass
class MonthlySummary:
    """Summary of a month's finances."""

    total_balance: float
    monthly_income: float
    monthly_expense: float
    transaction_count: int
