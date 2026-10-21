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


def test_default_categories_use_paper_colors(tmp_path: Path) -> None:
    colors = {
        category.name: category.color
        for category in Database(tmp_path / "test.db").get_categories()
    }

    assert colors["Salary"] == "#1F7A4D"
    assert colors["Food & drink"] == "#B4543C"
    assert colors["Other"] == "#9A9A94"


def test_legacy_default_colors_are_migrated(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    Database(db_path)

    connection = sqlite3.connect(db_path)
    connection.execute(
        "UPDATE categories SET color = '#1abc9c' WHERE name = 'Investments'"
    )
    connection.execute(
        "UPDATE categories SET color = '#c0392b' WHERE name = 'Housing'"
    )
    connection.commit()
    connection.close()

    migrated = Database(db_path)
    colors = {category.name: category.color for category in migrated.get_categories()}

    assert colors["Investments"] == "#35766E"
    assert colors["Housing"] == "#46587A"


def test_custom_category_colors_are_kept(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    Database(db_path)

    connection = sqlite3.connect(db_path)
    connection.execute("UPDATE categories SET color = '#123456' WHERE name = 'Housing'")
    connection.commit()
    connection.close()

    migrated = Database(db_path)
    colors = {category.name: category.color for category in migrated.get_categories()}

    assert colors["Housing"] == "#123456"
