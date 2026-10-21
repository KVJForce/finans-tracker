"""Dashboard-vy med översikt och diagram."""

from __future__ import annotations

from datetime import date
from typing import Optional

import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from finans_tracker.database import Database
from finans_tracker.theme import ThemeManager
from finans_tracker.ui.components import StatCard, format_currency


class DashboardView(ctk.CTkFrame):
    """Visar ekonomisk översikt och utgiftsdiagram."""

    MONTH_NAMES = [
        "", "Januari", "Februari", "Mars", "April", "Maj", "Juni",
        "Juli", "Augusti", "September", "Oktober", "November", "December",
    ]

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        db: Database,
        theme: ThemeManager,
        **kwargs,
    ) -> None:
        colors = theme.colors
        super().__init__(master, fg_color="transparent", **kwargs)
        self.db = db
        self.theme = theme
        self._current_date = date.today()
        self._stat_cards: dict[str, StatCard] = {}
        self._figure: Optional[Figure] = None
        self._canvas: Optional[FigureCanvasTkAgg] = None

        self._build_ui(colors)
        self.refresh()

    def _build_ui(self, colors: dict[str, str]) -> None:
        """Bygger dashboard-layout."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(24, 16))

        title = ctk.CTkLabel(
            header,
            text="Dashboard",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=colors["text_primary"],
        )
        title.pack(side="left")

        self._month_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=16),
            text_color=colors["text_secondary"],
        )
        self._month_label.pack(side="right")

        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=24, pady=(0, 16))
        cards_frame.columnconfigure((0, 1, 2), weight=1, uniform="cards")

        self._stat_cards["balance"] = StatCard(
            cards_frame, self.theme, "Total balans", value_color=colors["accent"]
        )
        self._stat_cards["balance"].grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        self._stat_cards["income"] = StatCard(
            cards_frame, self.theme, "Inkomster denna månad", value_color=colors["success"]
        )
        self._stat_cards["income"].grid(row=0, column=1, padx=8, sticky="nsew")

        self._stat_cards["expense"] = StatCard(
            cards_frame, self.theme, "Utgifter denna månad", value_color=colors["danger"]
        )
        self._stat_cards["expense"].grid(row=0, column=2, padx=(8, 0), sticky="nsew")

        chart_container = ctk.CTkFrame(
            self,
            fg_color=colors["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=colors["border"],
        )
        chart_container.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        chart_header = ctk.CTkLabel(
            chart_container,
            text="Utgifter per kategori",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=colors["text_primary"],
        )
        chart_header.pack(anchor="w", padx=20, pady=(16, 8))

        self._chart_frame = ctk.CTkFrame(chart_container, fg_color="transparent")
        self._chart_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._empty_label = ctk.CTkLabel(
            self._chart_frame,
            text="Inga utgifter denna månad",
            font=ctk.CTkFont(size=14),
            text_color=colors["text_muted"],
        )

    def refresh(self) -> None:
        """Uppdaterar alla dashboard-data."""
        colors = self.theme.colors
        year = self._current_date.year
        month = self._current_date.month

        self._month_label.configure(
            text=f"{self.MONTH_NAMES[month]} {year}"
        )

        summary = self.db.get_monthly_summary(year, month)
        self._stat_cards["balance"].set_value(
            format_currency(summary.total_balance),
            colors["accent"],
        )
        self._stat_cards["income"].set_value(
            format_currency(summary.monthly_income),
            colors["success"],
        )
        self._stat_cards["expense"].set_value(
            format_currency(summary.monthly_expense),
            colors["danger"],
        )

        self._update_chart(year, month)

    def _update_chart(self, year: int, month: int) -> None:
        """Ritar om utgiftsdiagrammet."""
        colors = self.theme.colors
        data = self.db.get_expenses_by_category(year, month)

        if self._canvas:
            self._canvas.get_tk_widget().destroy()
            self._canvas = None
        if self._figure:
            plt.close(self._figure)
            self._figure = None

        self._empty_label.pack_forget()

        if not data:
            self._empty_label.pack(expand=True)
            return

        names = [d[0] for d in data]
        amounts = [d[1] for d in data]
        chart_colors = [d[2] for d in data]

        self._figure = Figure(figsize=(7, 4), dpi=100)
        self._figure.patch.set_facecolor(colors["chart_bg"])
        ax = self._figure.add_subplot(111)
        ax.set_facecolor(colors["chart_bg"])

        wedges, texts, autotexts = ax.pie(
            amounts,
            labels=names,
            colors=chart_colors,
            autopct=lambda pct: f"{pct:.0f}%" if pct > 5 else "",
            startangle=90,
            pctdistance=0.75,
            textprops={"color": colors["chart_text"], "fontsize": 9},
        )
        for autotext in autotexts:
            autotext.set_color(colors["chart_text"])
            autotext.set_fontsize(8)

        ax.set_title(
            f"Totala utgifter: {format_currency(sum(amounts))}",
            color=colors["chart_text"],
            fontsize=12,
            pad=12,
        )

        self._figure.tight_layout()
        self._canvas = FigureCanvasTkAgg(self._figure, master=self._chart_frame)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

    def on_theme_change(self) -> None:
        """Uppdaterar vy vid temabyte."""
        self.refresh()
