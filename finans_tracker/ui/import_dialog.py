"""Dialog för att förhandsgranska och importera bank-CSV."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable, Optional

import customtkinter as ctk

from finans_tracker.database import Database, DatabaseError
from finans_tracker.importers import (
    CsvImportError,
    ImportPreview,
    build_transactions,
    load_import,
)
from finans_tracker.models import Category, CategoryType, TransactionType
from finans_tracker.theme import ThemeManager
from finans_tracker.ui.components import format_currency, show_error, show_info


class CategoryPicker(ctk.CTkToplevel):
    """Liten dialog för att byta kategori på en importerad rad."""

    def __init__(
        self,
        master: ctk.CTk,
        theme: ThemeManager,
        description: str,
        categories: list[Category],
        current: Optional[str],
        on_save: Callable[[str], None],
    ) -> None:
        super().__init__(master)
        colors = theme.colors
        self._on_save = on_save
        self._names = [category.name for category in categories]

        self.title("Byt kategori")
        self.geometry("400x230")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(
            self, text=description, wraplength=340,
            font=ctk.CTkFont(size=13),
            text_color=colors["text_secondary"],
        ).pack(padx=24, pady=(24, 8))

        self._var = ctk.StringVar(
            value=current if current in self._names else self._names[0]
        )
        ctk.CTkOptionMenu(
            self, variable=self._var, values=self._names, height=40,
        ).pack(fill="x", padx=24, pady=(0, 20))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=24)

        ctk.CTkButton(
            buttons, text="Avbryt", width=100, height=36,
            fg_color="transparent", border_width=1,
            border_color=colors["border"], text_color=colors["text_primary"],
            hover_color=colors["sidebar_hover"], command=self.destroy,
        ).pack(side="left")

        ctk.CTkButton(
            buttons, text="Spara", width=110, height=36,
            fg_color=colors["accent"], hover_color=colors["accent_hover"],
            command=self._save,
        ).pack(side="right")

        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_y() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _save(self) -> None:
        """Sparar vald kategori."""
        name = self._var.get()
        if name in self._names:
            self._on_save(name)
            self.destroy()


class ImportDialog(ctk.CTkToplevel):
    """Visar en CSV-fil och importerar valda transaktioner."""

    def __init__(
        self,
        master: ctk.CTk,
        db: Database,
        theme: ThemeManager,
        on_imported: Callable[[], None],
    ) -> None:
        super().__init__(master)
        colors = theme.colors
        self.db = db
        self.theme = theme
        self.on_imported = on_imported
        self.preview: Optional[ImportPreview] = None

        self.title("Importera bank-CSV")
        self.geometry("980x680")
        self.minsize(820, 560)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=colors["bg_primary"])

        self._build_ui(colors)

        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_y() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self, colors: dict[str, str]) -> None:
        """Bygger dialogens layout."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(
            container, text="Importera bank-CSV",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=colors["text_primary"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            container,
            text="Välj en CSV-export från din bank. Dubbletter hoppas över automatiskt.",
            font=ctk.CTkFont(size=13),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(2, 16))

        file_row = ctk.CTkFrame(container, fg_color="transparent")
        file_row.pack(fill="x", pady=(0, 12))

        ctk.CTkButton(
            file_row, text="Välj fil...", width=120, height=38,
            fg_color=colors["accent"], hover_color=colors["accent_hover"],
            command=self._choose_file,
        ).pack(side="left")

        file_info = ctk.CTkFrame(file_row, fg_color="transparent")
        file_info.pack(side="left", padx=12)

        self._file_label = ctk.CTkLabel(
            file_info, text="Ingen fil vald",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=colors["text_primary"], anchor="w",
        )
        self._file_label.pack(anchor="w")

        self._meta_label = ctk.CTkLabel(
            file_info, text="",
            font=ctk.CTkFont(size=11),
            text_color=colors["text_muted"], anchor="w",
            wraplength=680, justify="left",
        )
        self._meta_label.pack(anchor="w")

        summary = ctk.CTkFrame(container, fg_color="transparent")
        summary.pack(fill="x", pady=(0, 8))

        self._rows_label = self._summary_label(summary, colors, "0 rader")
        self._duplicates_label = self._summary_label(
            summary, colors, "0 dubbletter", colors["warning"]
        )
        self._new_label = self._summary_label(
            summary, colors, "0 att importera", colors["success"]
        )

        tree_frame = ctk.CTkFrame(
            container, fg_color=colors["bg_card"], corner_radius=12,
            border_width=1, border_color=colors["border"],
        )
        tree_frame.pack(fill="both", expand=True)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self._style_tree(colors)
        self._tree = ttk.Treeview(
            tree_frame,
            columns=("date", "description", "type", "amount", "category"),
            show="headings",
            style="Import.Treeview",
            selectmode="browse",
        )
        self._tree.heading("date", text="Datum")
        self._tree.heading("description", text="Beskrivning")
        self._tree.heading("type", text="Typ")
        self._tree.heading("amount", text="Belopp")
        self._tree.heading("category", text="Kategori")

        self._tree.column("date", width=95, anchor="w", stretch=False)
        self._tree.column("description", width=380, anchor="w")
        self._tree.column("type", width=80, anchor="w", stretch=False)
        self._tree.column("amount", width=120, anchor="e", stretch=False)
        self._tree.column("category", width=150, anchor="w", stretch=False)

        self._tree.tag_configure("duplicate", foreground=colors["text_muted"])
        self._tree.tag_configure("income", foreground=colors["success"])
        self._tree.tag_configure("expense", foreground=colors["text_primary"])

        scrollbar = ctk.CTkScrollbar(
            tree_frame, command=self._tree.yview,
            button_color=colors["border"], button_hover_color=colors["accent"],
        )
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)

        self._tree.bind("<Double-1>", self._on_double_click)

        self._warning_label = ctk.CTkLabel(
            container, text="", wraplength=900, justify="left",
            font=ctk.CTkFont(size=12),
            text_color=colors["warning"], anchor="w",
        )
        self._warning_label.pack(fill="x", pady=(8, 0))

        footer = ctk.CTkFrame(container, fg_color="transparent")
        footer.pack(fill="x", pady=(12, 0))

        ctk.CTkLabel(
            footer,
            text="Dubbelklicka på en rad för att byta kategori.",
            font=ctk.CTkFont(size=12),
            text_color=colors["text_muted"],
        ).pack(side="left")

        self._import_btn = ctk.CTkButton(
            footer, text="Importera", width=180, height=40,
            fg_color=colors["accent"], hover_color=colors["accent_hover"],
            state="disabled", command=self._import,
        )
        self._import_btn.pack(side="right")

        ctk.CTkButton(
            footer, text="Avbryt", width=100, height=40,
            fg_color="transparent", border_width=1,
            border_color=colors["border"], text_color=colors["text_primary"],
            hover_color=colors["sidebar_hover"], command=self.destroy,
        ).pack(side="right", padx=(0, 8))

    @staticmethod
    def _summary_label(
        master: ctk.CTkFrame,
        colors: dict[str, str],
        text: str,
        color: Optional[str] = None,
    ) -> ctk.CTkLabel:
        """Skapar en etikett i sammanfattningsraden."""
        label = ctk.CTkLabel(
            master, text=text,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=color or colors["text_secondary"],
        )
        label.pack(side="left", padx=(0, 18))
        return label

    def _style_tree(self, colors: dict[str, str]) -> None:
        """Anpassar ttk-trädet till appens tema."""
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            "Import.Treeview",
            background=colors["bg_card"],
            fieldbackground=colors["bg_card"],
            foreground=colors["text_primary"],
            borderwidth=0,
            rowheight=30,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Import.Treeview.Heading",
            background=colors["bg_secondary"],
            foreground=colors["text_secondary"],
            relief="flat",
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Import.Treeview",
            background=[("selected", colors["sidebar_hover"])],
            foreground=[("selected", colors["text_primary"])],
        )

    def _choose_file(self) -> None:
        """Öppnar filväljaren och läser den valda filen."""
        filepath = filedialog.askopenfilename(
            parent=self,
            title="Välj bank-CSV",
            initialdir=str(Path.home()),
            filetypes=[("CSV-filer", "*.csv"), ("Alla filer", "*.*")],
        )
        if not filepath:
            return
        self._load(Path(filepath))

    def _load(self, path: Path) -> None:
        """Tolkar filen och fyller förhandsvisningen."""
        try:
            self.preview = load_import(path, self.db)
        except CsvImportError as exc:
            show_error(self, self.theme, str(exc))
            return

        self._file_label.configure(text=path.name)
        self._meta_label.configure(
            text=f"{path.parent}  ·  {self.preview.encoding}  ·  separator {self.preview.delimiter!r}"
        )
        self._populate_tree()

    def _populate_tree(self) -> None:
        """Ritar om förhandsvisningen."""
        if self.preview is None:
            return

        colors = self.theme.colors
        self._tree.delete(*self._tree.get_children())
        self._tree.tag_configure("duplicate", foreground=colors["text_muted"])

        for index, item in enumerate(self.preview.transactions):
            is_income = item.transaction_type == TransactionType.INCOME
            prefix = "+" if is_income else "-"
            tag = (
                "duplicate"
                if item.is_duplicate
                else "income" if is_income else "expense"
            )
            self._tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    item.transaction_date.isoformat(),
                    item.description,
                    "Inkomst" if is_income else "Utgift",
                    f"{prefix}{format_currency(item.amount)}",
                    item.category_name or "—",
                ),
                tags=(tag,),
            )

        total = len(self.preview.transactions)
        duplicates = self.preview.duplicates
        importable = len(self.preview.importable)

        rows_text = f"{total} rad" if total == 1 else f"{total} rader"
        duplicates_text = (
            f"{duplicates} dubblett"
            if duplicates == 1
            else f"{duplicates} dubbletter"
        )

        self._rows_label.configure(text=rows_text)
        self._duplicates_label.configure(
            text=duplicates_text,
            text_color=colors["success"] if duplicates == 0 else colors["warning"],
        )
        self._new_label.configure(text=f"{importable} att importera")
        self._import_btn.configure(
            text=f"Importera {importable}",
            state="normal" if importable else "disabled",
        )

        if self.preview.skipped_rows:
            first_warning = (
                f" Första felet: {self.preview.warnings[0]}"
                if self.preview.warnings
                else ""
            )
            self._warning_label.configure(
                text=(
                    f"{self.preview.skipped_rows} rader hoppades över."
                    f"{first_warning}"
                )
            )
        else:
            self._warning_label.configure(text="")

    def _on_double_click(self, event) -> None:
        """Öppnar kategorival när en rad dubbelklickas."""
        item_id = self._tree.identify_row(event.y)
        if item_id:
            self._change_category(item_id)

    def _change_category(self, item_id: str) -> None:
        """Visar kategorival för en rad."""
        if self.preview is None:
            return

        try:
            transaction = self.preview.transactions[int(item_id)]
        except (ValueError, IndexError):
            return

        allowed = (
            CategoryType.INCOME
            if transaction.transaction_type == TransactionType.INCOME
            else CategoryType.EXPENSE
        )
        categories = [
            category
            for category in self.preview.categories
            if category.category_type in (allowed, CategoryType.BOTH)
        ]
        if not categories:
            show_error(
                self,
                self.theme,
                "Det finns ingen kategori som passar transaktionstypen.",
            )
            return

        def apply(name: str) -> None:
            transaction.category_name = name
            self._tree.set(item_id, "category", name)

        CategoryPicker(
            self,
            self.theme,
            transaction.description,
            categories,
            transaction.category_name,
            apply,
        )

    def _import(self) -> None:
        """Sparar de importerbara transaktionerna."""
        if self.preview is None:
            return

        try:
            transactions = build_transactions(self.preview)
            count = self.db.add_transactions(transactions)
        except (CsvImportError, DatabaseError) as exc:
            show_error(self, self.theme, str(exc))
            return

        message = f"{count} transaktioner importerade."
        if self.preview.duplicates:
            message += f"\n{self.preview.duplicates} dubbletter hoppades över."
        if self.preview.skipped_rows:
            message += f"\n{self.preview.skipped_rows} rader kunde inte läsas."

        root = self.master
        self.on_imported()
        self.destroy()
        show_info(root, self.theme, message)
