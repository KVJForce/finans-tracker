"""Återanvändbara UI-komponenter."""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from finans_tracker.theme import ThemeManager


def format_currency(amount: float) -> str:
    """
    Formaterar ett belopp som svensk valuta.

    Args:
        amount: Belopp att formatera.

    Returns:
        Formaterad sträng, t.ex. "1 234,56 kr".
    """
    sign = "-" if amount < 0 else ""
    abs_amount = abs(amount)
    integer_part = int(abs_amount)
    decimal_part = int(round((abs_amount - integer_part) * 100))
    formatted = f"{integer_part:,}".replace(",", " ")
    return f"{sign}{formatted},{decimal_part:02d} kr"


class StatCard(ctk.CTkFrame):
    """Kort som visar en nyckeltal med etikett."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        theme: ThemeManager,
        title: str,
        value: str = "0,00 kr",
        value_color: Optional[str] = None,
        **kwargs,
    ) -> None:
        colors = theme.colors
        super().__init__(
            master,
            fg_color=colors["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=colors["border"],
            **kwargs,
        )
        self._value_label: ctk.CTkLabel

        title_label = ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=13),
            text_color=colors["text_secondary"],
        )
        title_label.pack(anchor="w", padx=20, pady=(16, 4))

        self._value_label = ctk.CTkLabel(
            self,
            text=value,
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=value_color or colors["text_primary"],
        )
        self._value_label.pack(anchor="w", padx=20, pady=(0, 16))

    def set_value(self, value: str, color: Optional[str] = None) -> None:
        """Uppdaterar visat värde."""
        self._value_label.configure(text=value)
        if color:
            self._value_label.configure(text_color=color)


class SidebarButton(ctk.CTkButton):
    """Navigationsknapp i sidopanelen."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        theme: ThemeManager,
        text: str,
        icon: str,
        command: Callable[[], None],
        is_active: bool = False,
        **kwargs,
    ) -> None:
        colors = theme.colors
        super().__init__(
            master,
            text=f"  {icon}  {text}",
            command=command,
            anchor="w",
            height=44,
            corner_radius=8,
            font=ctk.CTkFont(size=14),
            fg_color=colors["sidebar_active"] if is_active else "transparent",
            hover_color=colors["sidebar_hover"],
            text_color=colors["text_primary"],
            **kwargs,
        )
        self._theme = theme
        self._is_active = is_active

    def set_active(self, active: bool) -> None:
        """Markerar knappen som aktiv/inaktiv."""
        self._is_active = active
        colors = self._theme.colors
        self.configure(
            fg_color=colors["sidebar_active"] if active else "transparent"
        )


class MessageDialog(ctk.CTkToplevel):
    """Enkel dialog för meddelanden och fel."""

    def __init__(
        self,
        master: ctk.CTk,
        theme: ThemeManager,
        title: str,
        message: str,
        is_error: bool = False,
    ) -> None:
        super().__init__(master)
        colors = theme.colors
        self.title(title)
        self.geometry("420x180")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        icon = "⚠" if is_error else "ℹ"
        icon_color = colors["danger"] if is_error else colors["accent"]

        icon_label = ctk.CTkLabel(
            self,
            text=icon,
            font=ctk.CTkFont(size=32),
            text_color=icon_color,
        )
        icon_label.pack(pady=(24, 8))

        msg_label = ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(size=14),
            text_color=colors["text_primary"],
            wraplength=360,
        )
        msg_label.pack(padx=24, pady=(0, 16))

        ok_btn = ctk.CTkButton(
            self,
            text="OK",
            width=100,
            command=self.destroy,
            fg_color=colors["accent"],
            hover_color=colors["accent_hover"],
        )
        ok_btn.pack(pady=(0, 20))

        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_y() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


class ConfirmDialog(ctk.CTkToplevel):
    """Bekräftelsedialog."""

    def __init__(
        self,
        master: ctk.CTk,
        theme: ThemeManager,
        title: str,
        message: str,
        on_confirm: Callable[[], None],
    ) -> None:
        super().__init__(master)
        colors = theme.colors
        self.title(title)
        self.geometry("420x200")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self._on_confirm = on_confirm

        msg_label = ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(size=14),
            text_color=colors["text_primary"],
            wraplength=360,
        )
        msg_label.pack(padx=24, pady=(32, 24))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(0, 24))

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Avbryt",
            width=100,
            fg_color="transparent",
            border_width=1,
            border_color=colors["border"],
            text_color=colors["text_primary"],
            hover_color=colors["sidebar_hover"],
            command=self.destroy,
        )
        cancel_btn.pack(side="left", padx=8)

        confirm_btn = ctk.CTkButton(
            btn_frame,
            text="Bekräfta",
            width=100,
            fg_color=colors["danger"],
            hover_color=colors["accent_hover"],
            command=self._confirm,
        )
        confirm_btn.pack(side="left", padx=8)

        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_y() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _confirm(self) -> None:
        self._on_confirm()
        self.destroy()


def show_error(master: ctk.CTk, theme: ThemeManager, message: str) -> None:
    """Visar ett felmeddelande."""
    MessageDialog(master, theme, "Fel", message, is_error=True)


def show_info(master: ctk.CTk, theme: ThemeManager, message: str) -> None:
    """Visar ett informationsmeddelande."""
    MessageDialog(master, theme, "Information", message, is_error=False)
