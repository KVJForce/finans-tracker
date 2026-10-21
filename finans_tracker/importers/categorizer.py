"""Automatisk kategorisering av transaktioner utifrån nyckelord."""

from __future__ import annotations

import re
from typing import Optional

from finans_tracker.importers.normalize import fold_text
from finans_tracker.importers.rules import DEFAULT_RULES
from finans_tracker.models import Category, CategoryType, TransactionType


def _searchable(value: str) -> str:
    """Gör text sökbar: gemener, utan diakriter och skiljetecken."""
    return re.sub(r"[^a-z0-9]+", " ", fold_text(value)).strip()


def _keyword_matches(text: str, keyword: str) -> bool:
    """Matchar ett nyckelord som ett helt ord i den sökbara texten."""
    folded = _searchable(keyword)
    return bool(folded) and f" {folded} " in f" {text} "


def suggest_category(
    description: str,
    transaction_type: TransactionType,
    categories: list[Category],
) -> Optional[str]:
    """
    Föreslår en kategori för en transaktion.

    Reglerna i ``rules.py`` matchas i ordning och första träffen vinner. Om
    ingen regel matchar används kategorin "Övrigt" när den finns.

    Args:
        description: Transaktionens beskrivning.
        transaction_type: Inkomst eller utgift.
        categories: Tillgängliga kategorier.

    Returns:
        Kategorinamn, eller None om ingen passande kategori finns.
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

    fallback = by_name.get(_searchable("Övrigt"))
    return fallback.name if fallback else None
