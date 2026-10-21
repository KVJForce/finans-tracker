"""Tests for database behavior and category name migration."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from finans_tracker.database import Database


def test_default_categories_are_english(tmp_path: Path) -> None:
    names = {
        category.name
        for category in Database(tmp_path / "test.db").get_categories()
    }

    assert {"Salary", "Food & drink", "Other"} <= names


def test_legacy_swedish_category_names_are_renamed(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    Database(db_path)

    connection = sqlite3.connect(db_path)
    connection.execute(
        "UPDATE categories SET name = 'Mat & dryck' WHERE name = 'Food & drink'"
    )
    connection.execute("UPDATE categories SET name = 'Övrigt' WHERE name = 'Other'")
    connection.commit()
    connection.close()

    migrated = Database(db_path)
    names = {category.name for category in migrated.get_categories()}

    assert "Food & drink" in names
    assert "Other" in names
    assert "Mat & dryck" not in names
    assert "Övrigt" not in names
