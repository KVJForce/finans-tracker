"""SQLite-databashantering för Finans Tracker."""

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
    ("Lön", "#2ecc71", "income"),
    ("Freelance", "#27ae60", "income"),
    ("Investeringar", "#1abc9c", "income"),
    ("Övrig inkomst", "#16a085", "income"),
    ("Mat & dryck", "#e74c3c", "expense"),
    ("Boende", "#c0392b", "expense"),
    ("Transport", "#e67e22", "expense"),
    ("Underhållning", "#9b59b6", "expense"),
    ("Shopping", "#3498db", "expense"),
    ("Hälsa", "#1abc9c", "expense"),
    ("Utbildning", "#2980b9", "expense"),
    ("Övrigt", "#95a5a6", "both"),
]


class DatabaseError(Exception):
    """Basfel för databasoperationer."""


class Database:
    """Hanterar all persistent lagring via SQLite."""

    def __init__(self, db_path: Path) -> None:
        """
        Initierar databasanslutning.

        Args:
            db_path: Sökväg till SQLite-databasfilen.
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Ger en databasanslutning med radfabriker."""
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
        """Skapar tabeller och standarddata om de saknas."""
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    color TEXT NOT NULL DEFAULT '#3498db',
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

    # --- Kategorier ---

    def get_categories(
        self, category_type: Optional[CategoryType] = None
    ) -> list[Category]:
        """
        Hämtar alla kategorier, valfritt filtrerade på typ.

        Args:
            category_type: Filtrera på inkomst, utgift eller båda.

        Returns:
            Lista med kategorier sorterade alfabetiskt.
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
        """Hämtar en kategori via ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM categories WHERE id = ?", (category_id,)
            ).fetchone()
        return self._row_to_category(row) if row else None

    def add_category(self, category: Category) -> int:
        """
        Skapar en ny kategori.

        Args:
            category: Kategori att spara.

        Returns:
            ID för den nya kategorin.

        Raises:
            DatabaseError: Om namnet redan finns.
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
            raise DatabaseError(f"Kategorin '{category.name}' finns redan.") from exc

    def update_category(self, category: Category) -> None:
        """
        Uppdaterar en befintlig kategori.

        Raises:
            DatabaseError: Om kategorin saknas eller namnet är upptaget.
        """
        if category.id is None:
            raise DatabaseError("Kategori-ID saknas.")
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
                    raise DatabaseError("Kategorin kunde inte hittas.")
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(f"Kategorin '{category.name}' finns redan.") from exc

    def delete_category(self, category_id: int) -> None:
        """
        Tar bort en kategori om den inte används.

        Raises:
            DatabaseError: Om kategorin har transaktioner eller saknas.
        """
        with self._connection() as conn:
            usage = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE category_id = ?",
                (category_id,),
            ).fetchone()[0]
            if usage > 0:
                raise DatabaseError(
                    "Kategorin kan inte tas bort eftersom den har transaktioner kopplade."
                )
            result = conn.execute(
                "DELETE FROM categories WHERE id = ?", (category_id,)
            )
            if result.rowcount == 0:
                raise DatabaseError("Kategorin kunde inte hittas.")

    def category_in_use(self, category_id: int) -> bool:
        """Kontrollerar om en kategori har transaktioner."""
        with self._connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE category_id = ?",
                (category_id,),
            ).fetchone()[0]
        return count > 0

    # --- Transaktioner ---

    def get_transactions(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        category_id: Optional[int] = None,
        transaction_type: Optional[TransactionType] = None,
    ) -> list[Transaction]:
        """
        Hämtar transaktioner med valfria filter.

        Args:
            date_from: Startdatum (inklusive).
            date_to: Slutdatum (inklusive).
            category_id: Filtrera på kategori.
            transaction_type: Filtrera på inkomst/utgift.

        Returns:
            Lista med transaktioner sorterade efter datum (nyast först).
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
        """Hämtar en transaktion via ID."""
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
        Skapar en ny transaktion.

        Returns:
            ID för den nya transaktionen.

        Raises:
            DatabaseError: Vid ogiltiga data.
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
            raise DatabaseError("Kunde inte spara transaktionen. Kontrollera kategorin.") from exc

    def add_transactions(self, transactions: list[Transaction]) -> int:
        """
        Sparar flera transaktioner i en gemensam databastransaktion.

        Args:
            transactions: Transaktioner att spara.

        Returns:
            Antal sparade transaktioner.

        Raises:
            DatabaseError: Om någon transaktion är ogiltig.
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
                "Kunde inte importera transaktionerna. Kontrollera kategorierna."
            ) from exc

        return len(transactions)

    def update_transaction(self, transaction: Transaction) -> None:
        """Uppdaterar en befintlig transaktion."""
        if transaction.id is None:
            raise DatabaseError("Transaktions-ID saknas.")
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
                    raise DatabaseError("Transaktionen kunde inte hittas.")
        except sqlite3.IntegrityError as exc:
            raise DatabaseError("Kunde inte uppdatera transaktionen.") from exc

    def delete_transaction(self, transaction_id: int) -> None:
        """Tar bort en transaktion."""
        with self._connection() as conn:
            result = conn.execute(
                "DELETE FROM transactions WHERE id = ?", (transaction_id,)
            )
            if result.rowcount == 0:
                raise DatabaseError("Transaktionen kunde inte hittas.")

    # --- Statistik ---

    def get_monthly_summary(self, year: int, month: int) -> MonthlySummary:
        """
        Beräknar ekonomisk sammanfattning för en given månad.

        Args:
            year: År (t.ex. 2026).
            month: Månad (1-12).

        Returns:
            MonthlySummary med balans och totalsummor.
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
        Hämtar utgifter grupperade per kategori för en månad.

        Returns:
            Lista med (kategorinamn, belopp, färg).
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

    # --- Inställningar ---

    def get_setting(self, key: str, default: str = "") -> str:
        """Hämtar en inställning."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """Sparar en inställning."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    # --- Hjälpmetoder ---

    @staticmethod
    def _validate_transaction(transaction: Transaction) -> None:
        """Validerar transaktionsdata."""
        if transaction.amount <= 0:
            raise DatabaseError("Beloppet måste vara större än noll.")
        if not transaction.description.strip():
            raise DatabaseError("Beskrivning får inte vara tom.")
        if transaction.category_id <= 0:
            raise DatabaseError("En giltig kategori måste väljas.")

    @staticmethod
    def _row_to_category(row: sqlite3.Row) -> Category:
        """Konverterar databasrad till Category."""
        return Category(
            id=row["id"],
            name=row["name"],
            color=row["color"],
            category_type=CategoryType(row["category_type"]),
        )

    @staticmethod
    def _row_to_transaction(row: sqlite3.Row) -> Transaction:
        """Konverterar databasrad till Transaction."""
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
