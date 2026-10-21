"""Temahantering för applikationen."""

from __future__ import annotations

from enum import Enum
from typing import Callable

import customtkinter as ctk


class ThemeMode(str, Enum):
    """Tillgängliga teman."""

    DARK = "dark"
    LIGHT = "light"


# Färgpalett per tema
THEME_COLORS = {
    ThemeMode.DARK: {
        "bg_primary": "#1a1a2e",
        "bg_secondary": "#16213e",
        "bg_card": "#0f3460",
        "accent": "#e94560",
        "accent_hover": "#ff6b6b",
        "success": "#2ecc71",
        "warning": "#f39c12",
        "danger": "#e74c3c",
        "text_primary": "#eaeaea",
        "text_secondary": "#a0a0a0",
        "text_muted": "#6c6c6c",
        "border": "#2a2a4a",
        "chart_bg": "#16213e",
        "chart_text": "#eaeaea",
        "sidebar_active": "#e94560",
        "sidebar_hover": "#1f4068",
    },
    ThemeMode.LIGHT: {
        "bg_primary": "#f5f6fa",
        "bg_secondary": "#ffffff",
        "bg_card": "#ffffff",
        "accent": "#6c5ce7",
        "accent_hover": "#5f4dd0",
        "success": "#00b894",
        "warning": "#fdcb6e",
        "danger": "#d63031",
        "text_primary": "#2d3436",
        "text_secondary": "#636e72",
        "text_muted": "#b2bec3",
        "border": "#dfe6e9",
        "chart_bg": "#ffffff",
        "chart_text": "#2d3436",
        "sidebar_active": "#6c5ce7",
        "sidebar_hover": "#dfe6e9",
    },
}


class ThemeManager:
    """Central hantering av ljust/mörkt tema."""

    SETTING_KEY = "theme_mode"

    def __init__(self, on_change: Callable[[ThemeMode], None] | None = None) -> None:
        """
        Initierar temahanteraren.

        Args:
            on_change: Callback som anropas vid temabyte.
        """
        self._mode = ThemeMode.DARK
        self._on_change = on_change

    @property
    def mode(self) -> ThemeMode:
        """Aktuellt tema."""
        return self._mode

    @property
    def colors(self) -> dict[str, str]:
        """Färgpalett för aktuellt tema."""
        return THEME_COLORS[self._mode]

    def set_mode(self, mode: ThemeMode, notify: bool = True) -> None:
        """
        Byter tema och uppdaterar CustomTkinter.

        Args:
            mode: Nytt tema (dark/light).
            notify: Om True anropas on_change-callback (stäng av vid init).
        """
        self._mode = mode
        ctk.set_appearance_mode(mode.value)
        ctk.set_default_color_theme("blue")
        if notify and self._on_change:
            self._on_change(mode)

    def toggle(self) -> ThemeMode:
        """Växlar mellan ljust och mörkt tema."""
        new_mode = ThemeMode.LIGHT if self._mode == ThemeMode.DARK else ThemeMode.DARK
        self.set_mode(new_mode)
        return new_mode

    def load_from_setting(self, value: str, notify: bool = False) -> None:
        """
        Laddar tema från sparad inställning.

        Args:
            value: Sparat temavärde ('dark' eller 'light').
            notify: Om True anropas on_change-callback efter laddning.
        """
        try:
            self.set_mode(ThemeMode(value), notify=notify)
        except ValueError:
            self.set_mode(ThemeMode.DARK, notify=notify)
