"""SQLite database management for Finance Tracker."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Generator, Optional

from finans_tracker.models import (
    Category,
    CategoryType,
    MonthlySummary,
    Transaction,
    TransactionType,
)

DEFAULT_CATEGORIES: list[tuple[str, str, str]] = [
    ("Salary", "#1F7A4D", "income"),
    ("Freelance", "#2F8B69", "income"),
    ("Investments", "#35766E", "income"),
    ("Other income", "#587F5A", "income"),
    ("Food & drink", "#B4543C", "expense"),
    ("Housing", "#46587A", "expense"),
    ("Transport", "#A87C2E", "expense"),
    ("Entertainment", "#7A5C8E", "expense"),
    ("Shopping", "#3E7F8C", "expense"),
    ("Health", "#7C9440", "expense"),
    ("Education", "#5A6FA8", "expense"),
    ("Other", "#9A9A94", "both"),
]

# Legacy Swedish names are renamed on startup so existing databases keep working.
LEGACY_CATEGORY_NAMES: dict[str, str] = {
    "Lön": "Salary",
    "Investeringar": "Investments",
    "Övrig inkomst": "Other income",
    "Mat & dryck": "Food & drink",
    "Boende": "Housing",
    "Underhållning": "Entertainment",
    "Hälsa": "Health",
    "Utbildning": "Education",
    "Övrigt": "Other",
}

# Legacy default colors are replaced with the paper palette on startup.
# Only rows that still use an original default color are touched.
LEGACY_CATEGORY_COLORS: dict[str, tuple[str, str]] = {
    "Salary": ("#2ecc71", "#1F7A4D"),
    "Freelance": ("#27ae60", "#2F8B69"),
    "Investments": ("#1abc9c", "#35766E"),
    "Other income": ("#16a085", "#587F5A"),
    "Food & drink": ("#e74c3c", "#B4543C"),
    "Housing": ("#c0392b", "#46587A"),
    "Transport": ("#e67e22", "#A87C2E"),
    "Entertainment": ("#9b59b6", "#7A5C8E"),
    "Shopping": ("#3498db", "#3E7F8C"),
    "Health": ("#1abc9c", "#7C9440"),
    "Education": ("#2980b9", "#5A6FA8"),
    "Other": ("#95a5a6", "#9A9A94"),
}


class DatabaseError(Exception):
    """Base error for database operations."""


class Database:
    """Handles all persistent storage through SQLite."""

    def __init__(self, db_path: Path) -> None:
        """
        Initializes the database connection.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Yields a database connection with row factories."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Creates tables and seeds default data when missing."""
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    color TEXT NOT NULL DEFAULT '#9A9A94',
                    category_type TEXT NOT NULL DEFAULT 'expense',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount REAL NOT NULL CHECK(amount > 0),
                    category_id INTEGER NOT NULL,
                    transaction_date TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    transaction_type TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_transactions_date
                    ON transactions(transaction_date);
                CREATE INDEX IF NOT EXISTS idx_transactions_category
                    ON transactions(category_id);
                CREATE INDEX IF NOT EXISTS idx_transactions_type
                    ON transactions(transaction_type);
                """
            )

            count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            if count == 0:
                for name, color, cat_type in DEFAULT_CATEGORIES:
                    conn.execute(
                        "INSERT INTO categories (name, color, category_type) VALUES (?, ?, ?)",
                        (name, color, cat_type),
                    )

            self._migrate_category_names(conn)
            self._migrate_category_colors(conn)

    @staticmethod
    def _migrate_category_names(conn: sqlite3.Connection) -> None:
        """Renames legacy Swedish default categories to their English names."""
        existing = {row["name"] for row in conn.execute("SELECT name FROM categories")}
        for old_name, new_name in LEGACY_CATEGORY_NAMES.items():
            if old_name in existing and new_name not in existing:
                conn.execute(
                    "UPDATE categories SET name = ? WHERE name = ?",
                    (new_name, old_name),
                )
                existing.discard(old_name)
                existing.add(new_name)

    @staticmethod
    def _migrate_category_colors(conn: sqlite3.Connection) -> None:
        """Replaces legacy default colors with the current paper palette."""
        for name, (old_color, new_color) in LEGACY_CATEGORY_COLORS.items():
            conn.execute(
                "UPDATE categories SET color = ? WHERE name = ? AND color = ?",
                (new_color, name, old_color),
            )

    # --- Categories ---

    def get_categories(
        self, category_type: Optional[CategoryType] = None
    ) -> list[Category]:
        """
        Fetches all categories, optionally filtered by type.

        Args:
            category_type: Filter by income, expense, or both.

        Returns:
            List of categories sorted alphabetically.
        """
        query = "SELECT * FROM categories"
        params: tuple = ()
        if category_type:
            query += " WHERE category_type = ? OR category_type = 'both'"
            params = (category_type.value,)
        query += " ORDER BY name COLLATE NOCASE"

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_category(row) for row in rows]

    def get_category(self, category_id: int) -> Optional[Category]:
        """Fetches a category by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM categories WHERE id = ?", (category_id,)
            ).fetchone()
        return self._row_to_category(row) if row else None

    def add_category(self, category: Category) -> int:
        """
        Creates a new category.

        Args:
            category: Category to save.

        Returns:
            ID of the new category.

        Raises:
            DatabaseError: If the name already exists.
        """
        try:
            with self._connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO categories (name, color, category_type)
                    VALUES (?, ?, ?)
                    """,
                    (category.name.strip(), category.color, category.category_type.value),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(f"Category '{category.name}' already exists.") from exc

    def update_category(self, category: Category) -> None:
        """
        Updates an existing category.

        Raises:
            DatabaseError: If the category is missing or the name is taken.
        """
        if category.id is None:
            raise DatabaseError("Category ID is missing.")
        try:
            with self._connection() as conn:
                result = conn.execute(
                    """
                    UPDATE categories SET name = ?, color = ?, category_type = ?
                    WHERE id = ?
                    """,
                    (
                        category.name.strip(),
                        category.color,
                        category.category_type.value,
                        category.id,
                    ),
                )
                if result.rowcount == 0:
                    raise DatabaseError("Category could not be found.")
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(f"Category '{category.name}' already exists.") from exc

    def delete_category(self, category_id: int) -> None:
        """
        Deletes a category if it is not in use.

        Raises:
            DatabaseError: If the category has transactions or is missing.
        """
        with self._connection() as conn:
            usage = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE category_id = ?",
                (category_id,),
            ).fetchone()[0]
            if usage > 0:
                raise DatabaseError(
                    "The category cannot be deleted because it has linked transactions."
                )
            result = conn.execute(
                "DELETE FROM categories WHERE id = ?", (category_id,)
            )
            if result.rowcount == 0:
                raise DatabaseError("Category could not be found.")

    def category_in_use(self, category_id: int) -> bool:
        """Checks whether a category has transactions."""
        with self._connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE category_id = ?",
                (category_id,),
            ).fetchone()[0]
        return count > 0

    # --- Transactions ---

    def get_transactions(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        category_id: Optional[int] = None,
        transaction_type: Optional[TransactionType] = None,
    ) -> list[Transaction]:
        """
        Fetches transactions with optional filters.

        Args:
            date_from: Start date (inclusive).
            date_to: End date (inclusive).
            category_id: Filter by category.
            transaction_type: Filter by income or expense.

        Returns:
            List of transactions sorted by date (newest first).
        """
        query = """
            SELECT t.*, c.name AS category_name, c.color AS category_color
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE 1=1
        """
        params: list = []

        if date_from:
            query += " AND t.transaction_date >= ?"
            params.append(date_from.isoformat())
        if date_to:
            query += " AND t.transaction_date <= ?"
            params.append(date_to.isoformat())
        if category_id:
            query += " AND t.category_id = ?"
            params.append(category_id)
        if transaction_type:
            query += " AND t.transaction_type = ?"
            params.append(transaction_type.value)

        query += " ORDER BY t.transaction_date DESC, t.id DESC"

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_transaction(row) for row in rows]

    def get_transaction(self, transaction_id: int) -> Optional[Transaction]:
        """Fetches a transaction by ID."""
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT t.*, c.name AS category_name, c.color AS category_color
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE t.id = ?
                """,
                (transaction_id,),
            ).fetchone()
        return self._row_to_transaction(row) if row else None

    def add_transaction(self, transaction: Transaction) -> int:
        """
        Creates a new transaction.

        Returns:
            ID of the new transaction.

        Raises:
            DatabaseError: On invalid data.
        """
        self._validate_transaction(transaction)
        try:
            with self._connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO transactions
                        (amount, category_id, transaction_date, description, transaction_type)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        abs(transaction.amount),
                        transaction.category_id,
                        transaction.transaction_date.isoformat(),
                        transaction.description.strip(),
                        transaction.transaction_type.value,
                    ),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise DatabaseError("Could not save the transaction. Check the category.") from exc

    def add_transactions(self, transactions: list[Transaction]) -> int:
        """
        Saves multiple transactions in a single database transaction.

        Args:
            transactions: Transactions to save.

        Returns:
            Number of saved transactions.

        Raises:
            DatabaseError: If any transaction is invalid.
        """
        if not transactions:
            return 0

        for transaction in transactions:
            self._validate_transaction(transaction)

        try:
            with self._connection() as conn:
                conn.executemany(
                    """
                    INSERT INTO transactions
                        (amount, category_id, transaction_date, description, transaction_type)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            abs(transaction.amount),
                            transaction.category_id,
                            transaction.transaction_date.isoformat(),
                            transaction.description.strip(),
                            transaction.transaction_type.value,
                        )
                        for transaction in transactions
                    ],
                )
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(
                "Could not import the transactions. Check the categories."
            ) from exc

        return len(transactions)

    def update_transaction(self, transaction: Transaction) -> None:
        """Updates an existing transaction."""
        if transaction.id is None:
            raise DatabaseError("Transaction ID is missing.")
        self._validate_transaction(transaction)
        try:
            with self._connection() as conn:
                result = conn.execute(
                    """
                    UPDATE transactions
                    SET amount = ?, category_id = ?, transaction_date = ?,
                        description = ?, transaction_type = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (
                        abs(transaction.amount),
                        transaction.category_id,
                        transaction.transaction_date.isoformat(),
                        transaction.description.strip(),
                        transaction.transaction_type.value,
                        transaction.id,
                    ),
                )
                if result.rowcount == 0:
                    raise DatabaseError("Transaction could not be found.")
        except sqlite3.IntegrityError as exc:
            raise DatabaseError("Could not update the transaction.") from exc

    def delete_transaction(self, transaction_id: int) -> None:
        """Deletes a transaction."""
        with self._connection() as conn:
            result = conn.execute(
                "DELETE FROM transactions WHERE id = ?", (transaction_id,)
            )
            if result.rowcount == 0:
                raise DatabaseError("Transaction could not be found.")

    # --- Statistics ---

    def get_monthly_summary(self, year: int, month: int) -> MonthlySummary:
        """
        Calculates a financial summary for a given month.

        Args:
            year: Year (e.g. 2026).
            month: Month (1-12).

        Returns:
            MonthlySummary with balance and totals.
        """
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, month + 1, 1)

        with self._connection() as conn:
            income = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) FROM transactions
                WHERE transaction_type = 'income'
                  AND transaction_date >= ? AND transaction_date < ?
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchone()[0]

            expense = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) FROM transactions
                WHERE transaction_type = 'expense'
                  AND transaction_date >= ? AND transaction_date < ?
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchone()[0]

            count = conn.execute(
                """
                SELECT COUNT(*) FROM transactions
                WHERE transaction_date >= ? AND transaction_date < ?
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchone()[0]

            total_income = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE transaction_type = 'income'"
            ).fetchone()[0]

            total_expense = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE transaction_type = 'expense'"
            ).fetchone()[0]

        return MonthlySummary(
            total_balance=float(total_income) - float(total_expense),
            monthly_income=float(income),
            monthly_expense=float(expense),
            transaction_count=int(count),
        )

    def get_expenses_by_category(
        self, year: int, month: int
    ) -> list[tuple[str, float, str]]:
        """
        Fetches expenses grouped by category for a month.

        Returns:
            List of (category name, amount, color).
        """
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, month + 1, 1)

        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT c.name, SUM(t.amount) AS total, c.color
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE t.transaction_type = 'expense'
                  AND t.transaction_date >= ? AND t.transaction_date < ?
                GROUP BY c.id
                ORDER BY total DESC
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()

        return [(row["name"], float(row["total"]), row["color"]) for row in rows]

    # --- Settings ---

    def get_setting(self, key: str, default: str = "") -> str:
        """Fetches a setting."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """Saves a setting."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    # --- Helpers ---

    @staticmethod
    def _validate_transaction(transaction: Transaction) -> None:
        """Validates transaction data."""
        if transaction.amount <= 0:
            raise DatabaseError("Amount must be greater than zero.")
        if not transaction.description.strip():
            raise DatabaseError("Description cannot be empty.")
        if transaction.category_id <= 0:
            raise DatabaseError("A valid category must be selected.")

    @staticmethod
    def _row_to_category(row: sqlite3.Row) -> Category:
        """Converts a database row to a Category."""
        return Category(
            id=row["id"],
            name=row["name"],
            color=row["color"],
            category_type=CategoryType(row["category_type"]),
        )

    @staticmethod
    def _row_to_transaction(row: sqlite3.Row) -> Transaction:
        """Converts a database row to a Transaction."""
        return Transaction(
            id=row["id"],
            amount=row["amount"],
            category_id=row["category_id"],
            transaction_date=date.fromisoformat(row["transaction_date"]),
            description=row["description"],
            transaction_type=TransactionType(row["transaction_type"]),
            category_name=row["category_name"] if "category_name" in row.keys() else None,
            category_color=row["category_color"] if "category_color" in row.keys() else None,
        )
