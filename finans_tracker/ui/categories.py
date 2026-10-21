"""Categories view with CRUD and color coding."""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from finans_tracker.database import Database, DatabaseError
from finans_tracker.models import Category, CategoryType
from finans_tracker.theme import ThemeManager, ui_font
from finans_tracker.ui.components import (
    ConfirmDialog,
    ghost_button,
    paper_entry,
    primary_button,
    row_action_button,
    show_error,
)


PRESET_COLORS = [
    "#1F7A4D", "#2F8B69", "#35766E", "#587F5A", "#7C9440",
    "#46587A", "#5A6FA8", "#3E7F8C", "#7A5C8E", "#A87C2E",
    "#B4543C", "#8A4E5C", "#8C6E4F", "#9A9A94", "#1F1F1D",
]


class ColorPicker(ctk.CTkFrame):
    """Simple color picker with predefined colors."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        theme: ThemeManager,
        initial_color: str = "#1F7A4D",
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
                row_frame.pack(fill="x", pady=3)
            btn = ctk.CTkButton(
                row_frame, text="", width=32, height=32,
                fg_color=color, hover_color=color,
                corner_radius=16,
                command=lambda c=color: self._select(c),
            )
            btn.pack(side="left", padx=4)
            self._buttons.append(btn)

        self._select(initial_color)

    def _select(self, color: str) -> None:
        """Highlights the selected color."""
        self._selected = color
        for btn in self._buttons:
            btn_color = btn.cget("fg_color")
            btn.configure(
                border_width=2 if btn_color == color else 0,
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
        self.geometry("460x520")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=colors["bg_card"])

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=28, pady=26)

        ctk.CTkLabel(
            form,
            text="Edit category" if is_edit else "New category",
            font=ui_font(18, "bold"),
            text_color=colors["text_primary"],
        ).pack(anchor="w", pady=(0, 18))

        ctk.CTkLabel(
            form, text="NAME", font=ui_font(11, "bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 6))

        self._name_entry = paper_entry(form, theme, placeholder_text="Category name")
        self._name_entry.pack(fill="x", pady=(0, 16))
        if category:
            self._name_entry.insert(0, category.name)

        ctk.CTkLabel(
            form, text="TYPE", font=ui_font(11, "bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 6))

        self._type_var = ctk.StringVar(
            value=category.category_type.value if category else "expense"
        )
        type_frame = ctk.CTkFrame(form, fg_color="transparent")
        type_frame.pack(fill="x", pady=(0, 16))

        for label, value in [("Expense", "expense"), ("Income", "income"), ("Both", "both")]:
            ctk.CTkRadioButton(
                type_frame, text=label, variable=self._type_var, value=value,
                font=ui_font(13),
                fg_color=colors["accent"], border_color=colors["border"],
                hover_color=colors["accent_hover"],
                text_color=colors["text_primary"],
            ).pack(side="left", padx=(0, 16))

        ctk.CTkLabel(
            form, text="COLOR", font=ui_font(11, "bold"),
            text_color=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 6))

        self._color_picker = ColorPicker(
            form, theme,
            initial_color=category.color if category else PRESET_COLORS[0],
        )
        self._color_picker.pack(fill="x", pady=(0, 22))

        btn_frame = ctk.CTkFrame(form, fg_color="transparent")
        btn_frame.pack(fill="x")

        ghost_button(
            btn_frame, theme, "Cancel", self.destroy, width=104, height=38,
        ).pack(side="left")

        primary_button(
            btn_frame, theme, "Save", self._save, width=124, height=38,
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
        header.pack(fill="x", padx=28, pady=(26, 16))

        ctk.CTkLabel(
            header, text="Categories",
            font=ui_font(24, "bold"),
            text_color=colors["text_primary"],
        ).pack(side="left")

        primary_button(
            header, self.theme, "+ New category",
            self._open_add_dialog, width=150,
        ).pack(side="right")

        self._list_container = ctk.CTkScrollableFrame(
            self, fg_color=colors["bg_card"], corner_radius=10,
            border_width=1, border_color=colors["border"],
            scrollbar_button_color=colors["border"],
            scrollbar_button_hover_color=colors["text_muted"],
        )
        self._list_container.pack(fill="both", expand=True, padx=28, pady=(0, 26))

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
                font=ui_font(13),
                text_color=colors["text_muted"],
            )
            empty.pack(pady=48)
            self._rows.append(empty)
            return

        for cat in categories:
            self._rows.append(self._create_row(cat))

    def _create_row(self, cat: Category) -> ctk.CTkFrame:
        """Creates a row in the category list."""
        colors = self.theme.colors

        row = ctk.CTkFrame(self._list_container, fg_color="transparent", height=58)
        row.pack(fill="x", padx=8, pady=1)
        row.pack_propagate(False)

        color_indicator = ctk.CTkFrame(
            row, width=22, height=22, corner_radius=11, fg_color=cat.color,
        )
        color_indicator.pack(side="left", padx=(14, 12), pady=18)

        info_frame = ctk.CTkFrame(row, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, pady=10)

        ctk.CTkLabel(
            info_frame, text=cat.name,
            font=ui_font(13, "bold"),
            text_color=colors["text_primary"], anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            info_frame, text=cat.display_type,
            font=ui_font(12),
            text_color=colors["text_secondary"], anchor="w",
        ).pack(anchor="w")

        in_use = self.db.category_in_use(cat.id) if cat.id else False

        if in_use:
            ctk.CTkButton(
                row, text="In use", width=68, height=28,
                corner_radius=6, font=ui_font(12),
                fg_color="transparent",
                text_color=colors["text_muted"],
                text_color_disabled=colors["text_muted"],
                state="disabled",
            ).pack(side="right", padx=(0, 10))
        else:
            row_action_button(
                row, self.theme, "Delete",
                lambda c=cat: self._confirm_delete(c), danger=True,
            ).pack(side="right", padx=(0, 10))

        row_action_button(
            row, self.theme, "Edit",
            lambda c=cat: self._open_edit_dialog(c),
        ).pack(side="right", padx=(0, 2))

        separator = ctk.CTkFrame(row, height=1, fg_color=colors["hairline"])
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
        """Rebuilds the view when the theme changes."""
        for child in self.winfo_children():
            child.destroy()
        self._rows.clear()
        self._build_ui(self.theme.colors)
        self.refresh()
