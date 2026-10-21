"""Automatic categorization of transactions based on keywords."""

from __future__ import annotations

import re
from typing import Optional

from finans_tracker.importers.normalize import fold_text
from finans_tracker.importers.rules import DEFAULT_RULES
from finans_tracker.models import Category, CategoryType, TransactionType


def _searchable(value: str) -> str:
    """Makes text searchable: lowercase, without diacritics or punctuation."""
    return re.sub(r"[^a-z0-9]+", " ", fold_text(value)).strip()


def _keyword_matches(text: str, keyword: str) -> bool:
    """Matches a keyword as a whole word in the searchable text."""
    folded = _searchable(keyword)
    return bool(folded) and f" {folded} " in f" {text} "


def suggest_category(
    description: str,
    transaction_type: TransactionType,
    categories: list[Category],
) -> Optional[str]:
    """
    Suggests a category for a transaction.

    The rules in ``rules.py`` are matched in order and the first hit wins.
    When no rule matches, the category "Other" is used if it exists.

    Args:
        description: Description of the transaction.
        transaction_type: Income or expense.
        categories: Available categories.

    Returns:
        Category name, or None if no suitable category exists.
    """
    allowed = (
        CategoryType.INCOME
        if transaction_type == TransactionType.INCOME
        else CategoryType.EXPENSE
    )
    by_name = {
        _searchable(category.name): category
        for category in categories
        if category.category_type in (allowed, CategoryType.BOTH)
    }

    text = _searchable(description)
    for keywords, category_name in DEFAULT_RULES:
        if not any(_keyword_matches(text, keyword) for keyword in keywords):
            continue
        category = by_name.get(_searchable(category_name))
        if category:
            return category.name

    fallback = by_name.get(_searchable("Other"))
    return fallback.name if fallback else None
