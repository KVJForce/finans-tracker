"""Categories view with CRUD and color coding."""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from finans_tracker.database import Database, DatabaseError
from finans_tracker.models import Category, CategoryType
from finans_tracker.theme import ThemeManager
from finans_tracker.ui.components import ConfirmDialog, show_error


PRESET_COLORS = [
    "#e74c3c", "#e67e22", "#f39c12", "#2ecc71", "#27ae60",
    "#1abc9c", "#3498db", "#2980b9", "#9b59b6", "#8e44ad",
    "#e94560", "#6c5ce7", "#00b894", "#fdcb6e", "#636e72",
]


class ColorPicker(ctk.CTkFrame):
    """Simple color picker with predefined colors."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        theme: ThemeManager,
        initial_color: str = "#3498db",
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.theme = theme
        self._selected = initial_color
        self._buttons: list[ctk.CTkButton] = []

        row_frame: Optional[ctk.CTkFrame] = None
        for i, color in enumerate(PRESET_COLORS):
            if i % 5 == 0:
                row_frame = ctk.CTkFrame(self, fg_color="transparent")
                row_frame.pack(fill="x", pady=2)
            btn = ctk.CTkButton(
                row_frame, text="", width=36, height=36,
                fg_color=color, hover_color=color,
                corner_radius=18,
                command=lambda c=color: self._select(c),
            )
            btn.pack(side="left", padx=3)
            self._buttons.append(btn)

        self._select(initial_color)

    def _select(self, color: str) -> None:
        """Highlights the selected color."""
        self._selected = color
        for btn in self._buttons:
            btn_color = btn.cget("fg_color")
            btn.configure(
                border_width=3 if btn_color == color else 0,
                border_color=self.theme.colors["text_primary"],
            )

    @property
    def selected_color(self) -> str:
        """Returns the selected color."""
        return self._selected


class CategoryDialog(ctk.CTkToplevel):
    """Dialog for adding/editing categories."""

    def __init__(
        self,
        master: ctk.CTk,
        db: Database,
        theme: ThemeManager,
        on_save: Callable[[], None],
        category: Optional[Category] = None,
    ) -> None:
        super().__init__(master)
        colors = theme.colors
        self.db = db
        self.theme = theme
        self.on_save = on_save
        self.category = category

        is_edit = category is not None
        self.title("Edit category" if is_edit else "New category")
        self.geometry("440x480")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(
            form, text="Name", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 4))

        self._name_entry = ctk.CTkEntry(form, height=40, placeholder_text="Category name")
        self._name_entry.pack(fill="x", pady=(0, 12))
        if category:
            self._name_entry.insert(0, category.name)

        ctk.CTkLabel(
            form, text="Type", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 4))

        self._type_var = ctk.StringVar(
            value=category.category_type.value if category else "expense"
        )
        type_frame = ctk.CTkFrame(form, fg_color="transparent")
        type_frame.pack(fill="x", pady=(0, 12))

        for label, value in [("Expense", "expense"), ("Income", "income"), ("Both", "both")]:
            ctk.CTkRadioButton(
                type_frame, text=label, variable=self._type_var, value=value,
                text_color=colors["text_primary"],
            ).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            form, text="Color", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 4))

        self._color_picker = ColorPicker(
            form, theme,
            initial_color=category.color if category else "#3498db",
        )
        self._color_picker.pack(fill="x", pady=(0, 20))

        btn_frame = ctk.CTkFrame(form, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(
            btn_frame, text="Cancel", width=100, height=40,
            fg_color="transparent", border_width=1, border_color=colors["border"],
            text_color=colors["text_primary"], hover_color=colors["sidebar_hover"],
            command=self.destroy,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="Save", width=120, height=40,
            fg_color=colors["accent"], hover_color=colors["accent_hover"],
            command=self._save,
        ).pack(side="right")

        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_y() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _save(self) -> None:
        """Validates and saves the category."""
        name = self._name_entry.get().strip()
        if not name:
            show_error(self, self.theme, "Name cannot be empty.")
            return

        cat = Category(
            id=self.category.id if self.category else None,
            name=name,
            color=self._color_picker.selected_color,
            category_type=CategoryType(self._type_var.get()),
        )

        try:
            if self.category:
                self.db.update_category(cat)
            else:
                self.db.add_category(cat)
            self.on_save()
            self.destroy()
        except DatabaseError as exc:
            show_error(self, self.theme, str(exc))


class CategoriesView(ctk.CTkFrame):
    """Handles displaying and managing categories."""

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
        """Builds the categories layout."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(24, 16))

        ctk.CTkLabel(
            header, text="Categories",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=colors["text_primary"],
        ).pack(side="left")

        ctk.CTkButton(
            header, text="+ New category", height=40,
            fg_color=colors["accent"], hover_color=colors["accent_hover"],
            command=self._open_add_dialog,
        ).pack(side="right")

        self._list_container = ctk.CTkScrollableFrame(
            self, fg_color=colors["bg_card"], corner_radius=12,
            border_width=1, border_color=colors["border"],
        )
        self._list_container.pack(fill="both", expand=True, padx=24, pady=(0, 24))

    def refresh(self) -> None:
        """Reloads the category list."""
        colors = self.theme.colors
        for row in self._rows:
            row.destroy()
        self._rows.clear()

        categories = self.db.get_categories()
        if not categories:
            empty = ctk.CTkLabel(
                self._list_container,
                text="No categories",
                font=ctk.CTkFont(size=14),
                text_color=colors["text_muted"],
            )
            empty.pack(pady=40)
            self._rows.append(empty)
            return

        for cat in categories:
            self._rows.append(self._create_row(cat))

    def _create_row(self, cat: Category) -> ctk.CTkFrame:
        """Creates a row in the category list."""
        colors = self.theme.colors

        row = ctk.CTkFrame(self._list_container, fg_color="transparent", height=56)
        row.pack(fill="x", padx=8, pady=2)
        row.pack_propagate(False)

        color_indicator = ctk.CTkFrame(
            row, width=24, height=24, corner_radius=12, fg_color=cat.color,
        )
        color_indicator.pack(side="left", padx=(12, 12), pady=16)

        info_frame = ctk.CTkFrame(row, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, pady=8)

        ctk.CTkLabel(
            info_frame, text=cat.name,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=colors["text_primary"], anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            info_frame, text=cat.display_type,
            font=ctk.CTkFont(size=12),
            text_color=colors["text_secondary"], anchor="w",
        ).pack(anchor="w")

        in_use = self.db.category_in_use(cat.id) if cat.id else False
        delete_tooltip = " (in use)" if in_use else ""

        ctk.CTkButton(
            row, text="✎", width=32, height=32,
            fg_color="transparent", hover_color=colors["sidebar_hover"],
            text_color=colors["text_secondary"],
            command=lambda c=cat: self._open_edit_dialog(c),
        ).pack(side="right", padx=2)

        delete_btn = ctk.CTkButton(
            row, text=f"✕{delete_tooltip}", width=32 if not in_use else 80, height=32,
            fg_color="transparent",
            hover_color=colors["danger"] if not in_use else colors["sidebar_hover"],
            text_color=colors["text_muted"] if in_use else colors["text_secondary"],
            state="disabled" if in_use else "normal",
            command=lambda c=cat: self._confirm_delete(c),
        )
        delete_btn.pack(side="right", padx=2)

        separator = ctk.CTkFrame(row, height=1, fg_color=colors["border"])
        separator.place(relx=0, rely=1, relwidth=1)

        return row

    def _open_add_dialog(self) -> None:
        """Opens the dialog for a new category."""
        CategoryDialog(self.root, self.db, self.theme, on_save=self.refresh)

    def _open_edit_dialog(self, cat: Category) -> None:
        """Opens the dialog to edit a category."""
        CategoryDialog(
            self.root, self.db, self.theme,
            on_save=self.refresh, category=cat,
        )

    def _confirm_delete(self, cat: Category) -> None:
        """Confirms deleting a category."""
        ConfirmDialog(
            self.root, self.theme,
            title="Delete category",
            message=f"Are you sure you want to delete the category \"{cat.name}\"?",
            on_confirm=lambda: self._delete(cat),
        )

    def _delete(self, cat: Category) -> None:
        """Deletes a category."""
        try:
            if cat.id:
                self.db.delete_category(cat.id)
                self.refresh()
        except DatabaseError as exc:
            show_error(self.root, self.theme, str(exc))

    def on_theme_change(self) -> None:
        """Refreshes the view on theme change."""
        self.refresh()
