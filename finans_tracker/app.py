"""Huvudapplikation för Finans Tracker."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Optional

import customtkinter as ctk

from finans_tracker import __version__
from finans_tracker.backup import BackupManager
from finans_tracker.database import Database
from finans_tracker.export import ExportError, export_transactions_to_csv
from finans_tracker.theme import ThemeManager, ThemeMode
from finans_tracker.ui.categories import CategoriesView
from finans_tracker.ui.components import SidebarButton, show_error, show_info
from finans_tracker.ui.dashboard import DashboardView
from finans_tracker.ui.transactions import TransactionsView


class FinansTrackerApp(ctk.CTk):
    """Huvudfönster för Finans Tracker."""

    APP_NAME = "Finans Tracker"
    MIN_WIDTH = 960
    MIN_HEIGHT = 640

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        super().__init__()

        self.data_dir = data_dir or Path.home() / ".finans_tracker"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = self.data_dir / "finans.db"

        self.db = Database(db_path)
        self.backup_manager = BackupManager(db_path)

        self.theme_manager = ThemeManager(on_change=self._on_theme_change)
        saved_theme = self.db.get_setting("theme_mode", "dark")
        self.theme_manager.load_from_setting(saved_theme)

        self._current_view: str = "dashboard"
        self._sidebar_buttons: dict[str, SidebarButton] = {}
        self._views: dict[str, ctk.CTkFrame] = {}

        self._setup_window()
        self._build_ui()
        self._create_backup_on_startup()
        self._show_view("dashboard")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_window(self) -> None:
        """Konfigurerar huvudfönstret."""
        self.title(f"{self.APP_NAME} v{__version__}")
        self.geometry("1100x720")
        self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)

        colors = self.theme_manager.colors
        self.configure(fg_color=colors["bg_primary"])

    def _build_ui(self) -> None:
        """Bygger hela gränssnittet."""
        colors = self.theme_manager.colors

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar(colors)
        self._build_content_area(colors)

    def _build_sidebar(self, colors: dict[str, str]) -> None:
        """Bygger sidopanelen med navigation."""
        sidebar = ctk.CTkFrame(
            self, width=220, corner_radius=0,
            fg_color=colors["bg_secondary"],
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=16, pady=(24, 32))

        ctk.CTkLabel(
            logo_frame, text="💰",
            font=ctk.CTkFont(size=32),
        ).pack(anchor="w")

        ctk.CTkLabel(
            logo_frame, text=self.APP_NAME,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=colors["text_primary"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            logo_frame, text="Personlig ekonomi",
            font=ctk.CTkFont(size=12),
            text_color=colors["text_secondary"],
        ).pack(anchor="w")

        nav_items = [
            ("dashboard", "Dashboard", "📊"),
            ("transactions", "Transaktioner", "💳"),
            ("categories", "Kategorier", "🏷"),
        ]

        nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=12)

        for view_id, label, icon in nav_items:
            btn = SidebarButton(
                nav_frame, self.theme_manager, label, icon,
                command=lambda v=view_id: self._show_view(v),
                is_active=view_id == "dashboard",
            )
            btn.pack(fill="x", pady=2)
            self._sidebar_buttons[view_id] = btn

        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        tools_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        tools_frame.pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkButton(
            tools_frame, text="📤  Exportera CSV", height=36,
            anchor="w", fg_color="transparent",
            hover_color=colors["sidebar_hover"],
            text_color=colors["text_secondary"],
            command=self._export_csv,
        ).pack(fill="x", pady=2)

        ctk.CTkButton(
            tools_frame, text="💾  Skapa backup", height=36,
            anchor="w", fg_color="transparent",
            hover_color=colors["sidebar_hover"],
            text_color=colors["text_secondary"],
            command=self._manual_backup,
        ).pack(fill="x", pady=2)

        self._theme_btn = ctk.CTkButton(
            tools_frame,
            text="🌙  Mörkt tema" if self.theme_manager.mode == ThemeMode.DARK else "☀  Ljust tema",
            height=36, anchor="w", fg_color="transparent",
            hover_color=colors["sidebar_hover"],
            text_color=colors["text_secondary"],
            command=self._toggle_theme,
        )
        self._theme_btn.pack(fill="x", pady=2)

        version_label = ctk.CTkLabel(
            sidebar, text=f"v{__version__}",
            font=ctk.CTkFont(size=11),
            text_color=colors["text_muted"],
        )
        version_label.pack(pady=(0, 16))

    def _build_content_area(self, colors: dict[str, str]) -> None:
        """Bygger innehållsområdet med alla vyer."""
        self._content = ctk.CTkFrame(self, fg_color=colors["bg_primary"], corner_radius=0)
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        self._views["dashboard"] = DashboardView(
            self._content, self.db, self.theme_manager,
        )
        self._views["transactions"] = TransactionsView(
            self._content, self.db, self.theme_manager, root=self,
        )
        self._views["categories"] = CategoriesView(
            self._content, self.db, self.theme_manager, root=self,
        )

    def _show_view(self, view_id: str) -> None:
        """Byter aktiv vy."""
        for vid, view in self._views.items():
            if vid == view_id:
                view.grid(row=0, column=0, sticky="nsew")
                if hasattr(view, "refresh"):
                    view.refresh()
            else:
                view.grid_forget()

        for vid, btn in self._sidebar_buttons.items():
            btn.set_active(vid == view_id)

        self._current_view = view_id

    def _toggle_theme(self) -> None:
        """Växlar mellan ljust och mörkt tema."""
        new_mode = self.theme_manager.toggle()
        self.db.set_setting("theme_mode", new_mode.value)
        label = "🌙  Mörkt tema" if new_mode == ThemeMode.DARK else "☀  Ljust tema"
        self._theme_btn.configure(text=label)

    def _on_theme_change(self, mode: ThemeMode) -> None:
        """Uppdaterar UI vid temabyte."""
        if not hasattr(self, "_content"):
            return

        colors = self.theme_manager.colors
        self.configure(fg_color=colors["bg_primary"])
        self._content.configure(fg_color=colors["bg_primary"])

        for view in self._views.values():
            if hasattr(view, "on_theme_change"):
                view.on_theme_change()

    def _export_csv(self) -> None:
        """Exporterar transaktioner till CSV."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"transaktioner_{timestamp}.csv"

        filepath = filedialog.asksaveasfilename(
            parent=self,
            title="Exportera transaktioner",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV-filer", "*.csv"), ("Alla filer", "*.*")],
        )
        if not filepath:
            return

        try:
            count = export_transactions_to_csv(self.db, Path(filepath))
            show_info(self, self.theme_manager, f"{count} transaktioner exporterade till:\n{filepath}")
        except ExportError as exc:
            show_error(self, self.theme_manager, str(exc))

    def _create_backup_on_startup(self) -> None:
        """Skapar automatisk backup vid uppstart."""
        try:
            last_backup = self.db.get_setting("last_backup", "")
            today = datetime.now().strftime("%Y-%m-%d")

            if last_backup != today:
                backup_path = self.backup_manager.create_backup()
                self.db.set_setting("last_backup", today)
                self.db.set_setting("last_backup_path", str(backup_path))
        except (FileNotFoundError, OSError):
            pass

    def _manual_backup(self) -> None:
        """Skapar manuell backup."""
        try:
            backup_path = self.backup_manager.create_backup()
            self.db.set_setting("last_backup", datetime.now().strftime("%Y-%m-%d"))
            show_info(
                self, self.theme_manager,
                f"Backup skapad:\n{backup_path}",
            )
        except (FileNotFoundError, OSError) as exc:
            show_error(self, self.theme_manager, f"Backup misslyckades: {exc}")

    def _on_close(self) -> None:
        """Hanterar avslutning med backup."""
        try:
            self.backup_manager.create_backup()
        except (FileNotFoundError, OSError):
            pass
        self.destroy()


def run_app(data_dir: Optional[Path] = None) -> None:
    """
    Startar Finans Tracker-applikationen.

    Args:
        data_dir: Valfri sökväg för datalagring.
    """
    app = FinansTrackerApp(data_dir=data_dir)
    app.mainloop()


def main() -> None:
    """Entry point för applikationen."""
    run_app()


if __name__ == "__main__":
    main()
