"""Theme management for the application."""

from __future__ import annotations

import tkinter.font as tkfont
from enum import Enum
from tkinter import ttk
from typing import Callable, Optional

import customtkinter as ctk


class ThemeMode(str, Enum):
    """Available themes."""

    DARK = "dark"
    LIGHT = "light"


# Crisp paper palette: ink text, paper-white surfaces, hairline borders.
THEME_COLORS = {
    ThemeMode.LIGHT: {
        "bg_primary": "#F6F6F3",
        "bg_secondary": "#FBFBF9",
        "bg_card": "#FFFFFF",
        "field": "#F2F1EC",
        "accent": "#1F1F1D",
        "accent_hover": "#3A3A36",
        "accent_text": "#FFFFFF",
        "success": "#1E7A4C",
        "warning": "#A8721B",
        "danger": "#B4422F",
        "danger_hover": "#9E3A29",
        "text_primary": "#1F1F1D",
        "text_secondary": "#5C5C55",
        "text_muted": "#6F6F68",
        "border": "#E5E4DE",
        "hairline": "#EBEAE4",
        "hover": "#EFEEE9",
        "active": "#E7E6E0",
        "chart_bg": "#FFFFFF",
        "chart_text": "#3A3A36",
        "chart_muted": "#8E8E85",
        "sidebar_active": "#E7E6E0",
        "sidebar_hover": "#EFEEE9",
    },
    ThemeMode.DARK: {
        "bg_primary": "#1B1B19",
        "bg_secondary": "#21211F",
        "bg_card": "#232321",
        "field": "#2C2C28",
        "accent": "#EDEBE4",
        "accent_hover": "#FFFFFF",
        "accent_text": "#1B1B19",
        "success": "#79C29B",
        "warning": "#D9A441",
        "danger": "#E08A72",
        "danger_hover": "#E8A18C",
        "text_primary": "#EBE9E1",
        "text_secondary": "#A6A399",
        "text_muted": "#8A877C",
        "border": "#3A3931",
        "hairline": "#2E2D28",
        "hover": "#2B2B27",
        "active": "#34332D",
        "chart_bg": "#232321",
        "chart_text": "#C9C6BB",
        "chart_muted": "#8A877C",
        "sidebar_active": "#34332D",
        "sidebar_hover": "#2B2B27",
    },
}

_FONT_CANDIDATES = ("Segoe UI", "Inter", "Helvetica Neue", "Arial", "Verdana")
_font_family: Optional[str] = None


def font_family() -> str:
    """Returns the first available UI font family."""
    global _font_family
    if _font_family is not None:
        return _font_family
    try:
        available = set(tkfont.families())
    except RuntimeError:
        # No root window yet; use the first candidate without caching.
        return _FONT_CANDIDATES[0]
    for candidate in _FONT_CANDIDATES:
        if candidate in available:
            _font_family = candidate
            break
    else:
        _font_family = "Arial"
    return _font_family


def ui_font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    """Creates an app font with the preferred family."""
    return ctk.CTkFont(family=font_family(), size=size, weight=weight)


def style_treeview(style: ttk.Style, name: str, colors: dict[str, str]) -> None:
    """Applies the paper look to a ttk.Treeview style."""
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(
        name,
        background=colors["bg_card"],
        fieldbackground=colors["bg_card"],
        foreground=colors["text_primary"],
        borderwidth=0,
        rowheight=32,
        font=(font_family(), 11),
    )
    style.configure(
        f"{name}.Heading",
        background=colors["field"],
        foreground=colors["text_secondary"],
        relief="flat",
        borderwidth=0,
        font=(font_family(), 10, "bold"),
    )
    style.map(
        name,
        background=[("selected", colors["active"])],
        foreground=[("selected", colors["text_primary"])],
    )


class ThemeManager:
    """Central management of the light/dark theme."""

    SETTING_KEY = "theme_mode"

    def __init__(self, on_change: Callable[[ThemeMode], None] | None = None) -> None:
        """
        Initializes the theme manager.

        Args:
            on_change: Callback invoked when the theme changes.
        """
        self._mode = ThemeMode.LIGHT
        self._on_change = on_change

    @property
    def mode(self) -> ThemeMode:
        """Current theme."""
        return self._mode

    @property
    def colors(self) -> dict[str, str]:
        """Color palette for the current theme."""
        return THEME_COLORS[self._mode]

    def set_mode(self, mode: ThemeMode, notify: bool = True) -> None:
        """
        Switches the theme and updates CustomTkinter.

        Args:
            mode: New theme (dark/light).
            notify: If True, the on_change callback is invoked (disabled during init).
        """
        self._mode = mode
        ctk.set_appearance_mode(mode.value)
        ctk.set_default_color_theme("blue")
        if notify and self._on_change:
            self._on_change(mode)

    def toggle(self) -> ThemeMode:
        """Toggles between light and dark theme."""
        new_mode = ThemeMode.LIGHT if self._mode == ThemeMode.DARK else ThemeMode.DARK
        self.set_mode(new_mode)
        return new_mode

    def load_from_setting(self, value: str, notify: bool = False) -> None:
        """
        Loads the theme from a saved setting.

        Args:
            value: Saved theme value ('dark' or 'light').
            notify: If True, the on_change callback is invoked after loading.
        """
        try:
            self.set_mode(ThemeMode(value), notify=notify)
        except ValueError:
            self.set_mode(ThemeMode.LIGHT, notify=notify)
