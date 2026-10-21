"""Transaction view with CRUD and filtering."""

from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from finans_tracker.database import Database, DatabaseError
from finans_tracker.models import CategoryType, Transaction, TransactionType
from finans_tracker.theme import ThemeManager, ui_font
from finans_tracker.ui.components import (
    ConfirmDialog,
    format_currency,
    ghost_button,
    paper_entry,
    paper_menu,
    primary_button,
    row_action_button,
    show_error,
)
from finans_tracker.ui.import_dialog import ImportDialog


class TransactionDialog(ctk.CTkToplevel):
    """Dialog for adding/editing transactions."""

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
        self.title("Edit transaction" if is_edit else "New transaction")
        self.geometry("480x560")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=colors["bg_card"])

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=28, pady=26)

        ctk.CTkLabel(
            form,
            text="Edit transaction" if is_edit else "New transaction",
            font=ui_font(18, "bold"),
            text_color=colors["text_primary"],
        ).pack(anchor="w", pady=(0, 18))

        # Type
        ctk.CTkLabel(
            form, text="TYPE", font=ui_font(11, "bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 6))

        self._type_var = ctk.StringVar(
            value=transaction.transaction_type.value if transaction else "expense"
        )
        type_frame = ctk.CTkFrame(form, fg_color="transparent")
        type_frame.pack(fill="x", pady=(0, 16))

        ctk.CTkRadioButton(
            type_frame, text="Expense", variable=self._type_var, value="expense",
            command=self._on_type_change,
            font=ui_font(13),
            fg_color=colors["accent"], border_color=colors["border"],
            hover_color=colors["accent_hover"],
            text_color=colors["text_primary"],
        ).pack(side="left", padx=(0, 18))

        ctk.CTkRadioButton(
            type_frame, text="Income", variable=self._type_var, value="income",
            command=self._on_type_change,
            font=ui_font(13),
            fg_color=colors["accent"], border_color=colors["border"],
            hover_color=colors["accent_hover"],
            text_color=colors["text_primary"],
        ).pack(side="left")

        # Amount
        ctk.CTkLabel(
            form, text="AMOUNT (KR)", font=ui_font(11, "bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 6))

        self._amount_entry = paper_entry(form, theme, placeholder_text="0,00")
        self._amount_entry.pack(fill="x", pady=(0, 16))
        if transaction:
            self._amount_entry.insert(0, f"{transaction.amount:.2f}".replace(".", ","))

        # Category
        ctk.CTkLabel(
            form, text="CATEGORY", font=ui_font(11, "bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 6))

        self._category_var = ctk.StringVar()
        self._category_menu = paper_menu(
            form, theme, variable=self._category_var, values=["Loading..."],
        )
        self._category_menu.pack(fill="x", pady=(0, 16))
        self._category_map: dict[str, int] = {}

        # Date
        ctk.CTkLabel(
            form, text="DATE (YYYY-MM-DD)", font=ui_font(11, "bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 6))

        self._date_entry = paper_entry(form, theme, placeholder_text="2026-01-15")
        self._date_entry.pack(fill="x", pady=(0, 16))
        if transaction:
            self._date_entry.insert(0, transaction.transaction_date.isoformat())
        else:
            self._date_entry.insert(0, date.today().isoformat())

        # Description
        ctk.CTkLabel(
            form, text="DESCRIPTION", font=ui_font(11, "bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 6))

        self._desc_entry = paper_entry(
            form, theme, placeholder_text="What is this transaction for?",
        )
        self._desc_entry.pack(fill="x", pady=(0, 22))
        if transaction:
            self._desc_entry.insert(0, transaction.description)

        # Buttons
        btn_frame = ctk.CTkFrame(form, fg_color="transparent")
        btn_frame.pack(fill="x")

        ghost_button(
            btn_frame, theme, "Cancel", self.destroy, width=104, height=38,
        ).pack(side="left")

        primary_button(
            btn_frame, theme, "Save", self._save, width=124, height=38,
        ).pack(side="right")

        self._load_categories()
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_y() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _on_type_change(self) -> None:
        """Reloads categories when the type changes."""
        self._load_categories()

    def _load_categories(self) -> None:
        """Fills the category menu based on the selected type."""
        tx_type = TransactionType(self._type_var.get())
        cat_type = (
            CategoryType.INCOME if tx_type == TransactionType.INCOME
            else CategoryType.EXPENSE
        )
        categories = self.db.get_categories(cat_type)
        self._category_map = {c.name: c.id for c in categories if c.id}
        names = list(self._category_map.keys())

        if not names:
            self._category_menu.configure(values=["No categories"])
            self._category_var.set("No categories")
            return

        self._category_menu.configure(values=names)
        if self.transaction and self.transaction.category_name in names:
            self._category_var.set(self.transaction.category_name)
        else:
            self._category_var.set(names[0])

    def _save(self) -> None:
        """Validates and saves the transaction."""
        try:
            amount_str = self._amount_entry.get().strip().replace(",", ".")
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError("The amount must be positive.")

            date_str = self._date_entry.get().strip()
            tx_date = date.fromisoformat(date_str)

            description = self._desc_entry.get().strip()
            if not description:
                raise ValueError("Description cannot be empty.")

            category_name = self._category_var.get()
            if category_name not in self._category_map:
                raise ValueError("Choose a valid category.")

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
    """Handles the display and filtering of transactions."""

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
        """Builds the transactions layout."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(26, 16))

        ctk.CTkLabel(
            header, text="Transactions",
            font=ui_font(24, "bold"),
            text_color=colors["text_primary"],
        ).pack(side="left")

        primary_button(
            header, self.theme, "+ New transaction",
            self._open_add_dialog, width=156,
        ).pack(side="right")

        ghost_button(
            header, self.theme, "Import CSV",
            self._open_import_dialog, width=120,
        ).pack(side="right", padx=(0, 10))

        # Filters
        filter_frame = ctk.CTkFrame(
            self, fg_color=colors["bg_card"], corner_radius=10,
            border_width=1, border_color=colors["border"],
        )
        filter_frame.pack(fill="x", padx=28, pady=(0, 14))

        filter_inner = ctk.CTkFrame(filter_frame, fg_color="transparent")
        filter_inner.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(
            filter_inner, text="From", font=ui_font(12),
            text_color=colors["text_secondary"],
        ).pack(side="left", padx=(0, 6))

        self._date_from = paper_entry(
            filter_inner, self.theme, width=112, height=32,
            placeholder_text="YYYY-MM-DD",
        )
        self._date_from.pack(side="left", padx=(0, 14))

        ctk.CTkLabel(
            filter_inner, text="To", font=ui_font(12),
            text_color=colors["text_secondary"],
        ).pack(side="left", padx=(0, 6))

        self._date_to = paper_entry(
            filter_inner, self.theme, width=112, height=32,
            placeholder_text="YYYY-MM-DD",
        )
        self._date_to.pack(side="left", padx=(0, 14))

        ctk.CTkLabel(
            filter_inner, text="Category", font=ui_font(12),
            text_color=colors["text_secondary"],
        ).pack(side="left", padx=(0, 6))

        self._filter_category_var = ctk.StringVar(value="All")
        self._filter_category = paper_menu(
            filter_inner, self.theme,
            variable=self._filter_category_var, values=["All"],
            width=150, height=32,
        )
        self._filter_category.pack(side="left", padx=(0, 14))

        primary_button(
            filter_inner, self.theme, "Filter", self.refresh,
            width=88, height=32,
        ).pack(side="left", padx=(0, 8))

        ghost_button(
            filter_inner, self.theme, "Clear", self._clear_filters,
            width=76, height=32,
        ).pack(side="left")

        # List
        self._list_container = ctk.CTkScrollableFrame(
            self, fg_color=colors["bg_card"], corner_radius=10,
            border_width=1, border_color=colors["border"],
            scrollbar_button_color=colors["border"],
            scrollbar_button_hover_color=colors["text_muted"],
        )
        self._list_container.pack(fill="both", expand=True, padx=28, pady=(0, 26))

        self._update_filter_categories()

    def _update_filter_categories(self) -> None:
        """Updates the category filter."""
        categories = self.db.get_categories()
        names = ["All"] + [c.name for c in categories]
        self._filter_category.configure(values=names)

    def _clear_filters(self) -> None:
        """Resets all filters."""
        self._date_from.delete(0, "end")
        self._date_to.delete(0, "end")
        self._filter_category_var.set("All")
        self.refresh()

    def _get_filters(self) -> tuple[Optional[date], Optional[date], Optional[int], bool]:
        """
        Reads filter values from the UI.

        Returns:
            Tuple with (date_from, date_to, category_id, is_valid).
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
            show_error(self.root, self.theme, "Invalid date format. Use YYYY-MM-DD.")
            return None, None, None, False

        cat_name = self._filter_category_var.get()
        if cat_name != "All":
            for cat in self.db.get_categories():
                if cat.name == cat_name and cat.id:
                    category_id = cat.id
                    break

        return date_from, date_to, category_id, True

    def refresh(self) -> None:
        """Reloads the transaction list."""
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
                text="No transactions found",
                font=ui_font(13),
                text_color=colors["text_muted"],
            )
            empty.pack(pady=48)
            self._rows.append(empty)
            return

        for tx in transactions:
            self._rows.append(self._create_row(tx))

    def _create_row(self, tx: Transaction) -> ctk.CTkFrame:
        """Creates a row in the transaction list."""
        colors = self.theme.colors
        is_income = tx.transaction_type == TransactionType.INCOME
        amount_color = colors["success"] if is_income else colors["danger"]
        prefix = "+" if is_income else "-"

        row = ctk.CTkFrame(self._list_container, fg_color="transparent", height=58)
        row.pack(fill="x", padx=8, pady=1)
        row.pack_propagate(False)

        color_dot = ctk.CTkFrame(
            row, width=8, height=8, corner_radius=4,
            fg_color=tx.category_color or colors["accent"],
        )
        color_dot.pack(side="left", padx=(14, 10), pady=25)

        info_frame = ctk.CTkFrame(row, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, pady=10)

        ctk.CTkLabel(
            info_frame, text=tx.description,
            font=ui_font(13, "bold"),
            text_color=colors["text_primary"], anchor="w",
        ).pack(anchor="w")

        meta = f"{tx.category_name}  ·  {tx.transaction_date.isoformat()}"
        ctk.CTkLabel(
            info_frame, text=meta, font=ui_font(12),
            text_color=colors["text_secondary"], anchor="w",
        ).pack(anchor="w")

        row_action_button(
            row, self.theme, "Delete",
            lambda t=tx: self._confirm_delete(t), danger=True,
        ).pack(side="right", padx=(0, 10))

        row_action_button(
            row, self.theme, "Edit",
            lambda t=tx: self._open_edit_dialog(t),
        ).pack(side="right", padx=(0, 2))

        ctk.CTkLabel(
            row, text=f"{prefix}{format_currency(tx.amount)}",
            font=ui_font(14, "bold"),
            text_color=amount_color,
        ).pack(side="right", padx=10)

        separator = ctk.CTkFrame(row, height=1, fg_color=colors["hairline"])
        separator.place(relx=0, rely=1, relwidth=1)

        return row

    def _open_add_dialog(self) -> None:
        """Opens the dialog for a new transaction."""
        TransactionDialog(self.root, self.db, self.theme, on_save=self.refresh)

    def _open_import_dialog(self) -> None:
        """Opens the dialog for CSV import."""
        ImportDialog(
            self.root,
            self.db,
            self.theme,
            on_imported=self.refresh,
        )

    def _open_edit_dialog(self, tx: Transaction) -> None:
        """Opens the dialog for editing a transaction."""
        TransactionDialog(
            self.root, self.db, self.theme,
            on_save=self.refresh, transaction=tx,
        )

    def _confirm_delete(self, tx: Transaction) -> None:
        """Confirms deletion of a transaction."""
        ConfirmDialog(
            self.root, self.theme,
            title="Delete transaction",
            message=f"Are you sure you want to delete \"{tx.description}\" ({format_currency(tx.amount)})?",
            on_confirm=lambda: self._delete(tx),
        )

    def _delete(self, tx: Transaction) -> None:
        """Deletes a transaction."""
        try:
            if tx.id:
                self.db.delete_transaction(tx.id)
                self.refresh()
        except DatabaseError as exc:
            show_error(self.root, self.theme, str(exc))

    def on_theme_change(self) -> None:
        """Rebuilds the view when the theme changes."""
        for child in self.winfo_children():
            child.destroy()
        self._rows.clear()
        self._build_ui(self.theme.colors)
        self.refresh()
