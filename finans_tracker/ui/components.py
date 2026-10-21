"""Reusable UI components."""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from finans_tracker.theme import ThemeManager, ui_font


def format_currency(amount: float) -> str:
    """
    Formats an amount as Swedish currency.

    Args:
        amount: Amount to format.

    Returns:
        Formatted string, e.g. "1 234,56 kr".
    """
    sign = "-" if amount < 0 else ""
    abs_amount = abs(amount)
    integer_part = int(abs_amount)
    decimal_part = int(round((abs_amount - integer_part) * 100))
    formatted = f"{integer_part:,}".replace(",", " ")
    return f"{sign}{formatted},{decimal_part:02d} kr"


def primary_button(
    master: ctk.CTkBaseClass,
    theme: ThemeManager,
    text: str,
    command: Optional[Callable[[], None]] = None,
    **kwargs,
) -> ctk.CTkButton:
    """Creates an ink-filled primary button."""
    colors = theme.colors
    options = dict(
        text=text,
        command=command,
        height=36,
        corner_radius=8,
        font=ui_font(13),
        fg_color=colors["accent"],
        hover_color=colors["accent_hover"],
        text_color=colors["accent_text"],
    )
    options.update(kwargs)
    return ctk.CTkButton(master, **options)


def ghost_button(
    master: ctk.CTkBaseClass,
    theme: ThemeManager,
    text: str,
    command: Optional[Callable[[], None]] = None,
    **kwargs,
) -> ctk.CTkButton:
    """Creates a quiet outline button."""
    colors = theme.colors
    options = dict(
        text=text,
        command=command,
        height=36,
        corner_radius=8,
        font=ui_font(13),
        fg_color="transparent",
        hover_color=colors["hover"],
        text_color=colors["text_primary"],
        border_width=1,
        border_color=colors["border"],
    )
    options.update(kwargs)
    return ctk.CTkButton(master, **options)


def danger_button(
    master: ctk.CTkBaseClass,
    theme: ThemeManager,
    text: str,
    command: Optional[Callable[[], None]] = None,
    **kwargs,
) -> ctk.CTkButton:
    """Creates a muted red button for destructive actions."""
    colors = theme.colors
    options = dict(
        text=text,
        command=command,
        height=36,
        corner_radius=8,
        font=ui_font(13),
        fg_color=colors["danger"],
        hover_color=colors["danger_hover"],
        text_color=colors["accent_text"],
    )
    options.update(kwargs)
    return ctk.CTkButton(master, **options)


def row_action_button(
    master: ctk.CTkBaseClass,
    theme: ThemeManager,
    text: str,
    command: Callable[[], None],
    danger: bool = False,
) -> ctk.CTkButton:
    """Creates a small text-only button for list rows."""
    colors = theme.colors
    return ctk.CTkButton(
        master,
        text=text,
        command=command,
        width=58 if len(text) < 6 else 68,
        height=28,
        corner_radius=6,
        font=ui_font(12),
        fg_color="transparent",
        hover_color=colors["hover"],
        text_color=colors["danger"] if danger else colors["text_secondary"],
    )


def paper_entry(
    master: ctk.CTkBaseClass,
    theme: ThemeManager,
    **kwargs,
) -> ctk.CTkEntry:
    """Creates an entry styled as a soft paper field."""
    colors = theme.colors
    options = dict(
        height=34,
        corner_radius=8,
        font=ui_font(13),
        fg_color=colors["field"],
        border_width=0,
        text_color=colors["text_primary"],
        placeholder_text_color=colors["text_muted"],
    )
    options.update(kwargs)
    return ctk.CTkEntry(master, **options)


def paper_menu(
    master: ctk.CTkBaseClass,
    theme: ThemeManager,
    values: Optional[list[str]] = None,
    variable: Optional[ctk.StringVar] = None,
    **kwargs,
) -> ctk.CTkOptionMenu:
    """Creates a dropdown styled as a soft paper field."""
    colors = theme.colors
    options = dict(
        values=values or [],
        variable=variable,
        height=34,
        corner_radius=8,
        font=ui_font(13),
        fg_color=colors["field"],
        button_color=colors["field"],
        button_hover_color=colors["hover"],
        text_color=colors["text_primary"],
        dropdown_fg_color=colors["bg_card"],
        dropdown_hover_color=colors["hover"],
        dropdown_text_color=colors["text_primary"],
        dropdown_font=ui_font(13),
    )
    options.update(kwargs)
    return ctk.CTkOptionMenu(master, **options)


class StatCard(ctk.CTkFrame):
    """Card that shows a key metric with a label."""

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
            corner_radius=10,
            border_width=1,
            border_color=colors["border"],
            **kwargs,
        )
        self._value_label: ctk.CTkLabel

        title_label = ctk.CTkLabel(
            self,
            text=title.upper(),
            font=ui_font(11, "bold"),
            text_color=colors["text_secondary"],
        )
        title_label.pack(anchor="w", padx=20, pady=(18, 6))

        self._value_label = ctk.CTkLabel(
            self,
            text=value,
            font=ui_font(26, "bold"),
            text_color=value_color or colors["text_primary"],
        )
        self._value_label.pack(anchor="w", padx=20, pady=(0, 18))

    def set_value(self, value: str, color: Optional[str] = None) -> None:
        """Updates the displayed value."""
        self._value_label.configure(text=value)
        if color:
            self._value_label.configure(text_color=color)


class SidebarButton(ctk.CTkButton):
    """Navigation button in the sidebar."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        theme: ThemeManager,
        text: str,
        command: Callable[[], None],
        is_active: bool = False,
        **kwargs,
    ) -> None:
        colors = theme.colors
        super().__init__(
            master,
            text=text,
            command=command,
            anchor="w",
            height=38,
            corner_radius=8,
            font=ui_font(13, "bold" if is_active else "normal"),
            fg_color=colors["sidebar_active"] if is_active else "transparent",
            hover_color=colors["sidebar_hover"],
            text_color=colors["text_primary"] if is_active else colors["text_secondary"],
            **kwargs,
        )
        self._theme = theme
        self._is_active = is_active

    def set_active(self, active: bool) -> None:
        """Marks the button as active/inactive."""
        self._is_active = active
        colors = self._theme.colors
        self.configure(
            fg_color=colors["sidebar_active"] if active else "transparent",
            text_color=colors["text_primary"] if active else colors["text_secondary"],
            font=ui_font(13, "bold" if active else "normal"),
        )


class MessageDialog(ctk.CTkToplevel):
    """Simple dialog for messages and errors."""

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
        self.geometry("440x220")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=colors["bg_card"])

        header = ctk.CTkLabel(
            self,
            text=title,
            font=ui_font(15, "bold"),
            text_color=colors["danger"] if is_error else colors["text_primary"],
        )
        header.pack(anchor="w", padx=26, pady=(24, 6))

        msg_label = ctk.CTkLabel(
            self,
            text=message,
            font=ui_font(13),
            text_color=colors["text_secondary"],
            wraplength=380,
            justify="left",
            anchor="w",
        )
        msg_label.pack(anchor="w", padx=26, pady=(0, 20))

        ok_btn = primary_button(self, theme, "OK", self.destroy, width=96)
        ok_btn.pack(anchor="e", padx=26, pady=(0, 24))

        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_y() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


class ConfirmDialog(ctk.CTkToplevel):
    """Confirmation dialog."""

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
        self.geometry("440x240")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=colors["bg_card"])
        self._on_confirm = on_confirm

        header = ctk.CTkLabel(
            self,
            text=title,
            font=ui_font(15, "bold"),
            text_color=colors["text_primary"],
        )
        header.pack(anchor="w", padx=26, pady=(24, 6))

        msg_label = ctk.CTkLabel(
            self,
            text=message,
            font=ui_font(13),
            text_color=colors["text_secondary"],
            wraplength=380,
            justify="left",
            anchor="w",
        )
        msg_label.pack(anchor="w", padx=26, pady=(0, 18))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=26, pady=(0, 24))

        cancel_btn = ghost_button(btn_frame, theme, "Cancel", self.destroy, width=100)
        cancel_btn.pack(side="right", padx=(8, 0))

        confirm_btn = danger_button(btn_frame, theme, "Delete", self._confirm, width=100)
        confirm_btn.pack(side="right")

        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_y() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _confirm(self) -> None:
        self._on_confirm()
        self.destroy()


def show_error(master: ctk.CTk, theme: ThemeManager, message: str) -> None:
    """Shows an error message."""
    MessageDialog(master, theme, "Error", message, is_error=True)


def show_info(master: ctk.CTk, theme: ThemeManager, message: str) -> None:
    """Shows an information message."""
    MessageDialog(master, theme, "Information", message, is_error=False)
