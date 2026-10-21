"""Dashboard view with overview and charts."""

from __future__ import annotations

from datetime import date
from typing import Optional

import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from finans_tracker.database import Database
from finans_tracker.theme import ThemeManager, font_family, ui_font
from finans_tracker.ui.components import StatCard, format_currency


class DashboardView(ctk.CTkFrame):
    """Shows a financial overview and expense chart."""

    MONTH_NAMES = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
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
        self._chart_canvas: Optional[FigureCanvasTkAgg] = None

        self._build_ui(colors)
        self.refresh()

    def _build_ui(self, colors: dict[str, str]) -> None:
        """Builds the dashboard layout."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(26, 18))

        title = ctk.CTkLabel(
            header,
            text="Dashboard",
            font=ui_font(24, "bold"),
            text_color=colors["text_primary"],
        )
        title.pack(side="left")

        self._month_label = ctk.CTkLabel(
            header,
            text="",
            font=ui_font(13),
            text_color=colors["text_muted"],
        )
        self._month_label.pack(side="right")

        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=28, pady=(0, 18))
        cards_frame.columnconfigure((0, 1, 2), weight=1, uniform="cards")

        self._stat_cards["balance"] = StatCard(
            cards_frame, self.theme, "Total balance"
        )
        self._stat_cards["balance"].grid(row=0, column=0, padx=(0, 14), sticky="nsew")

        self._stat_cards["income"] = StatCard(
            cards_frame, self.theme, "Income this month"
        )
        self._stat_cards["income"].grid(row=0, column=1, padx=(0, 14), sticky="nsew")

        self._stat_cards["expense"] = StatCard(
            cards_frame, self.theme, "Expenses this month"
        )
        self._stat_cards["expense"].grid(row=0, column=2, sticky="nsew")

        chart_container = ctk.CTkFrame(
            self,
            fg_color=colors["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=colors["border"],
        )
        chart_container.pack(fill="both", expand=True, padx=28, pady=(0, 28))

        chart_header = ctk.CTkFrame(chart_container, fg_color="transparent")
        chart_header.pack(fill="x", padx=22, pady=(18, 4))

        ctk.CTkLabel(
            chart_header,
            text="Expenses by category",
            font=ui_font(15, "bold"),
            text_color=colors["text_primary"],
        ).pack(side="left")

        self._chart_frame = ctk.CTkFrame(chart_container, fg_color="transparent")
        self._chart_frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self._empty_label = ctk.CTkLabel(
            self._chart_frame,
            text="No expenses this month",
            font=ui_font(13),
            text_color=colors["text_muted"],
        )

    def refresh(self) -> None:
        """Refreshes all dashboard data."""
        colors = self.theme.colors
        year = self._current_date.year
        month = self._current_date.month

        self._month_label.configure(
            text=f"{self.MONTH_NAMES[month]} {year}"
        )

        summary = self.db.get_monthly_summary(year, month)
        self._stat_cards["balance"].set_value(
            format_currency(summary.total_balance),
            colors["text_primary"],
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
        """Redraws the expense chart."""
        colors = self.theme.colors
        data = self.db.get_expenses_by_category(year, month)

        if self._chart_canvas:
            self._chart_canvas.get_tk_widget().destroy()
            self._chart_canvas = None
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

        self._figure = Figure(figsize=(7.4, 3.9), dpi=100)
        self._figure.patch.set_facecolor(colors["chart_bg"])
        ax = self._figure.add_axes([0.03, 0.04, 0.5, 0.92])
        ax.set_facecolor(colors["chart_bg"])

        wedges, _ = ax.pie(
            amounts,
            colors=chart_colors,
            startangle=90,
            counterclock=False,
            wedgeprops={
                "width": 0.34,
                "edgecolor": colors["chart_bg"],
                "linewidth": 2.5,
            },
        )

        total = sum(amounts)
        ax.text(
            0, 0.08, format_currency(total),
            ha="center", va="center",
            fontsize=11, fontweight="bold",
            color=colors["chart_text"],
            fontfamily=font_family(),
        )
        ax.text(
            0, -0.12, "expenses",
            ha="center", va="center",
            fontsize=8,
            color=colors["chart_muted"],
            fontfamily=font_family(),
        )

        labels = [
            f"{name}  {format_currency(amount)}"
            for name, amount in zip(names, amounts)
        ]
        legend = ax.legend(
            wedges,
            labels,
            loc="center left",
            bbox_to_anchor=(0.95, 0.5),
            frameon=False,
            handlelength=0.9,
            handleheight=0.9,
            labelspacing=0.7,
        )
        for text in legend.get_texts():
            text.set_color(colors["chart_text"])
            text.set_fontsize(9)
            text.set_fontfamily(font_family())

        self._chart_canvas = FigureCanvasTkAgg(self._figure, master=self._chart_frame)
        widget = self._chart_canvas.get_tk_widget()
        widget.configure(bg=colors["chart_bg"], highlightthickness=0)
        self._chart_canvas.draw()
        widget.pack(fill="both", expand=True)

    def on_theme_change(self) -> None:
        """Updates the view when the theme changes."""
        if self._figure:
            plt.close(self._figure)
        self._figure = None
        self._chart_canvas = None
        self._stat_cards.clear()

        for child in self.winfo_children():
            child.destroy()

        self._build_ui(self.theme.colors)
        self.refresh()
