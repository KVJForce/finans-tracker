"""Transaktionsvy med CRUD och filtrering."""

from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from finans_tracker.database import Database, DatabaseError
from finans_tracker.models import CategoryType, Transaction, TransactionType
from finans_tracker.theme import ThemeManager
from finans_tracker.ui.components import (
    ConfirmDialog,
    format_currency,
    show_error,
)
from finans_tracker.ui.import_dialog import ImportDialog


class TransactionDialog(ctk.CTkToplevel):
    """Dialog för att lägga till/redigera transaktioner."""

    def __init__(
        self,
        master: ctk.CTk,
        db: Database,
        theme: ThemeManager,
        on_save: Callable[[], None],
        transaction: Optional[Transaction] = None,
    ) -> None:
        super().__init__(master)
        colors = theme.colors
        self.db = db
        self.theme = theme
        self.on_save = on_save
        self.transaction = transaction
        self.result_saved = False

        is_edit = transaction is not None
        self.title("Redigera transaktion" if is_edit else "Ny transaktion")
        self.geometry("480x520")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=24, pady=24)

        # Typ
        ctk.CTkLabel(
            form, text="Typ", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 4))

        self._type_var = ctk.StringVar(
            value=transaction.transaction_type.value if transaction else "expense"
        )
        type_frame = ctk.CTkFrame(form, fg_color="transparent")
        type_frame.pack(fill="x", pady=(0, 12))

        ctk.CTkRadioButton(
            type_frame, text="Utgift", variable=self._type_var, value="expense",
            command=self._on_type_change,
            text_color=colors["text_primary"],
        ).pack(side="left", padx=(0, 16))

        ctk.CTkRadioButton(
            type_frame, text="Inkomst", variable=self._type_var, value="income",
            command=self._on_type_change,
            text_color=colors["text_primary"],
        ).pack(side="left")

        # Belopp
        ctk.CTkLabel(
            form, text="Belopp (kr)", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 4))

        self._amount_entry = ctk.CTkEntry(
            form, placeholder_text="0,00", height=40,
        )
        self._amount_entry.pack(fill="x", pady=(0, 12))
        if transaction:
            self._amount_entry.insert(0, f"{transaction.amount:.2f}".replace(".", ","))

        # Kategori
        ctk.CTkLabel(
            form, text="Kategori", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 4))

        self._category_var = ctk.StringVar()
        self._category_menu = ctk.CTkOptionMenu(
            form, variable=self._category_var, height=40, values=["Laddar..."],
        )
        self._category_menu.pack(fill="x", pady=(0, 12))
        self._category_map: dict[str, int] = {}

        # Datum
        ctk.CTkLabel(
            form, text="Datum (ÅÅÅÅ-MM-DD)", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 4))

        self._date_entry = ctk.CTkEntry(
            form, placeholder_text="2026-01-15", height=40,
        )
        self._date_entry.pack(fill="x", pady=(0, 12))
        if transaction:
            self._date_entry.insert(0, transaction.transaction_date.isoformat())
        else:
            self._date_entry.insert(0, date.today().isoformat())

        # Beskrivning
        ctk.CTkLabel(
            form, text="Beskrivning", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 4))

        self._desc_entry = ctk.CTkEntry(
            form, placeholder_text="Vad gäller transaktionen?", height=40,
        )
        self._desc_entry.pack(fill="x", pady=(0, 20))
        if transaction:
            self._desc_entry.insert(0, transaction.description)

        # Knappar
        btn_frame = ctk.CTkFrame(form, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(
            btn_frame, text="Avbryt", width=100, height=40,
            fg_color="transparent", border_width=1, border_color=colors["border"],
            text_color=colors["text_primary"], hover_color=colors["sidebar_hover"],
            command=self.destroy,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="Spara", width=120, height=40,
            fg_color=colors["accent"], hover_color=colors["accent_hover"],
            command=self._save,
        ).pack(side="right")

        self._load_categories()
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_y() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _on_type_change(self) -> None:
        """Laddar om kategorier vid typbyte."""
        self._load_categories()

    def _load_categories(self) -> None:
        """Fyller kategorimenyn baserat på vald typ."""
        tx_type = TransactionType(self._type_var.get())
        cat_type = (
            CategoryType.INCOME if tx_type == TransactionType.INCOME
            else CategoryType.EXPENSE
        )
        categories = self.db.get_categories(cat_type)
        self._category_map = {c.name: c.id for c in categories if c.id}
        names = list(self._category_map.keys())

        if not names:
            self._category_menu.configure(values=["Inga kategorier"])
            self._category_var.set("Inga kategorier")
            return

        self._category_menu.configure(values=names)
        if self.transaction and self.transaction.category_name in names:
            self._category_var.set(self.transaction.category_name)
        else:
            self._category_var.set(names[0])

    def _save(self) -> None:
        """Validerar och sparar transaktionen."""
        try:
            amount_str = self._amount_entry.get().strip().replace(",", ".")
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError("Beloppet måste vara positivt.")

            date_str = self._date_entry.get().strip()
            tx_date = date.fromisoformat(date_str)

            description = self._desc_entry.get().strip()
            if not description:
                raise ValueError("Beskrivning får inte vara tom.")

            category_name = self._category_var.get()
            if category_name not in self._category_map:
                raise ValueError("Välj en giltig kategori.")

            tx = Transaction(
                id=self.transaction.id if self.transaction else None,
                amount=amount,
                category_id=self._category_map[category_name],
                transaction_date=tx_date,
                description=description,
                transaction_type=TransactionType(self._type_var.get()),
            )

            if self.transaction:
                self.db.update_transaction(tx)
            else:
                self.db.add_transaction(tx)

            self.result_saved = True
            self.on_save()
            self.destroy()

        except ValueError as exc:
            show_error(self, self.theme, str(exc))
        except DatabaseError as exc:
            show_error(self, self.theme, str(exc))


class TransactionsView(ctk.CTkFrame):
    """Hanterar visning och filtrering av transaktioner."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        db: Database,
        theme: ThemeManager,
        root: ctk.CTk,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.db = db
        self.theme = theme
        self.root = root
        self._rows: list[ctk.CTkFrame] = []
        colors = theme.colors

        self._build_ui(colors)
        self.refresh()

    def _build_ui(self, colors: dict[str, str]) -> None:
        """Bygger transaktionslayout."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(24, 16))

        ctk.CTkLabel(
            header, text="Transaktioner",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=colors["text_primary"],
        ).pack(side="left")

        ctk.CTkButton(
            header, text="+ Ny transaktion", height=40,
            fg_color=colors["accent"], hover_color=colors["accent_hover"],
            command=self._open_add_dialog,
        ).pack(side="right")

        ctk.CTkButton(
            header, text="Importera CSV", height=40, width=130,
            fg_color="transparent", border_width=1, border_color=colors["border"],
            text_color=colors["text_primary"], hover_color=colors["sidebar_hover"],
            command=self._open_import_dialog,
        ).pack(side="right", padx=(0, 8))

        # Filter
        filter_frame = ctk.CTkFrame(
            self, fg_color=colors["bg_card"], corner_radius=12,
            border_width=1, border_color=colors["border"],
        )
        filter_frame.pack(fill="x", padx=24, pady=(0, 12))

        filter_inner = ctk.CTkFrame(filter_frame, fg_color="transparent")
        filter_inner.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(
            filter_inner, text="Från:", text_color=colors["text_secondary"],
        ).pack(side="left", padx=(0, 4))
        self._date_from = ctk.CTkEntry(filter_inner, width=110, placeholder_text="ÅÅÅÅ-MM-DD")
        self._date_from.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            filter_inner, text="Till:", text_color=colors["text_secondary"],
        ).pack(side="left", padx=(0, 4))
        self._date_to = ctk.CTkEntry(filter_inner, width=110, placeholder_text="ÅÅÅÅ-MM-DD")
        self._date_to.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            filter_inner, text="Kategori:", text_color=colors["text_secondary"],
        ).pack(side="left", padx=(0, 4))
        self._filter_category_var = ctk.StringVar(value="Alla")
        self._filter_category = ctk.CTkOptionMenu(
            filter_inner, variable=self._filter_category_var, width=140, values=["Alla"],
        )
        self._filter_category.pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            filter_inner, text="Filtrera", width=90, height=32,
            fg_color=colors["accent"], hover_color=colors["accent_hover"],
            command=self.refresh,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            filter_inner, text="Rensa", width=70, height=32,
            fg_color="transparent", border_width=1, border_color=colors["border"],
            text_color=colors["text_primary"], hover_color=colors["sidebar_hover"],
            command=self._clear_filters,
        ).pack(side="left")

        # Lista
        self._list_container = ctk.CTkScrollableFrame(
            self, fg_color=colors["bg_card"], corner_radius=12,
            border_width=1, border_color=colors["border"],
        )
        self._list_container.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        self._update_filter_categories()

    def _update_filter_categories(self) -> None:
        """Uppdaterar kategorifilter."""
        categories = self.db.get_categories()
        names = ["Alla"] + [c.name for c in categories]
        self._filter_category.configure(values=names)

    def _clear_filters(self) -> None:
        """Återställer alla filter."""
        self._date_from.delete(0, "end")
        self._date_to.delete(0, "end")
        self._filter_category_var.set("Alla")
        self.refresh()

    def _get_filters(self) -> tuple[Optional[date], Optional[date], Optional[int], bool]:
        """
        Läser filtervärden från UI.

        Returns:
            Tuple med (date_from, date_to, category_id, is_valid).
        """
        date_from: Optional[date] = None
        date_to: Optional[date] = None
        category_id: Optional[int] = None

        try:
            if self._date_from.get().strip():
                date_from = date.fromisoformat(self._date_from.get().strip())
            if self._date_to.get().strip():
                date_to = date.fromisoformat(self._date_to.get().strip())
        except ValueError:
            show_error(self.root, self.theme, "Ogiltigt datumformat. Använd ÅÅÅÅ-MM-DD.")
            return None, None, None, False

        cat_name = self._filter_category_var.get()
        if cat_name != "Alla":
            for cat in self.db.get_categories():
                if cat.name == cat_name and cat.id:
                    category_id = cat.id
                    break

        return date_from, date_to, category_id, True

    def refresh(self) -> None:
        """Laddar om transaktionslistan."""
        colors = self.theme.colors
        date_from, date_to, category_id, is_valid = self._get_filters()
        if not is_valid:
            return

        for row in self._rows:
            row.destroy()
        self._rows.clear()

        self._update_filter_categories()
        transactions = self.db.get_transactions(
            date_from=date_from, date_to=date_to, category_id=category_id,
        )

        if not transactions:
            empty = ctk.CTkLabel(
                self._list_container,
                text="Inga transaktioner hittades",
                font=ctk.CTkFont(size=14),
                text_color=colors["text_muted"],
            )
            empty.pack(pady=40)
            self._rows.append(empty)
            return

        for tx in transactions:
            self._rows.append(self._create_row(tx))

    def _create_row(self, tx: Transaction) -> ctk.CTkFrame:
        """Skapar en rad i transaktionslistan."""
        colors = self.theme.colors
        is_income = tx.transaction_type == TransactionType.INCOME
        amount_color = colors["success"] if is_income else colors["danger"]
        prefix = "+" if is_income else "-"

        row = ctk.CTkFrame(self._list_container, fg_color="transparent", height=56)
        row.pack(fill="x", padx=8, pady=2)
        row.pack_propagate(False)

        color_dot = ctk.CTkFrame(
            row, width=8, height=8, corner_radius=4,
            fg_color=tx.category_color or colors["accent"],
        )
        color_dot.pack(side="left", padx=(12, 8), pady=20)

        info_frame = ctk.CTkFrame(row, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, pady=8)

        ctk.CTkLabel(
            info_frame, text=tx.description,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=colors["text_primary"], anchor="w",
        ).pack(anchor="w")

        meta = f"{tx.category_name}  ·  {tx.transaction_date.isoformat()}"
        ctk.CTkLabel(
            info_frame, text=meta, font=ctk.CTkFont(size=12),
            text_color=colors["text_secondary"], anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            row, text=f"{prefix}{format_currency(tx.amount)}",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=amount_color,
        ).pack(side="right", padx=(8, 4))

        ctk.CTkButton(
            row, text="✎", width=32, height=32,
            fg_color="transparent", hover_color=colors["sidebar_hover"],
            text_color=colors["text_secondary"],
            command=lambda t=tx: self._open_edit_dialog(t),
        ).pack(side="right", padx=2)

        ctk.CTkButton(
            row, text="✕", width=32, height=32,
            fg_color="transparent", hover_color=colors["danger"],
            text_color=colors["text_secondary"],
            command=lambda t=tx: self._confirm_delete(t),
        ).pack(side="right", padx=2)

        separator = ctk.CTkFrame(row, height=1, fg_color=colors["border"])
        separator.place(relx=0, rely=1, relwidth=1)

        return row

    def _open_add_dialog(self) -> None:
        """Öppnar dialog för ny transaktion."""
        TransactionDialog(self.root, self.db, self.theme, on_save=self.refresh)

    def _open_import_dialog(self) -> None:
        """Öppnar dialog för CSV-import."""
        ImportDialog(
            self.root,
            self.db,
            self.theme,
            on_imported=self.refresh,
        )

    def _open_edit_dialog(self, tx: Transaction) -> None:
        """Öppnar dialog för att redigera transaktion."""
        TransactionDialog(
            self.root, self.db, self.theme,
            on_save=self.refresh, transaction=tx,
        )

    def _confirm_delete(self, tx: Transaction) -> None:
        """Bekräftar borttagning av transaktion."""
        ConfirmDialog(
            self.root, self.theme,
            title="Ta bort transaktion",
            message=f"Vill du ta bort \"{tx.description}\" ({format_currency(tx.amount)})?",
            on_confirm=lambda: self._delete(tx),
        )

    def _delete(self, tx: Transaction) -> None:
        """Tar bort en transaktion."""
        try:
            if tx.id:
                self.db.delete_transaction(tx.id)
                self.refresh()
        except DatabaseError as exc:
            show_error(self.root, self.theme, str(exc))

    def on_theme_change(self) -> None:
        """Uppdaterar vy vid temabyte."""
        self.refresh()
