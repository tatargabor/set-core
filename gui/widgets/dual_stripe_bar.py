"""
DualStripeBar - Compact dual-stripe progress bar widget.

Renders two stacked horizontal stripes (time elapsed on top, usage consumed
on bottom) in a single 10px-tall widget using QPainter.
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor

__all__ = ["DualStripeBar"]


class DualStripeBar(QWidget):
    """A compact widget that paints two horizontal progress stripes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(10)
        self._time_pct = 0.0
        self._usage_pct = 0.0
        self._time_color = QColor("#94a3b8")
        self._usage_color = QColor("#22c55e")
        self._bg_color = QColor("#e5e7eb")
        self._border_color = QColor("#cccccc")

    def set_values(self, time_pct: float, usage_pct: float):
        """Set both stripe percentages (0-100). Triggers repaint."""
        self._time_pct = min(max(time_pct, 0), 100)
        self._usage_pct = min(max(usage_pct, 0), 100)
        self.update()

    def set_colors(self, time_color: str, usage_color: str,
                   bg_color: str, border_color: str):
        """Set colors for the next paintEvent."""
        self._time_color = QColor(time_color)
        self._usage_color = QColor(usage_color)
        self._bg_color = QColor(bg_color)
        self._border_color = QColor(border_color)

    def set_empty(self, bg_color: str, border_color: str):
        """Reset to empty state (no fill)."""
        self._time_pct = 0.0
        self._usage_pct = 0.0
        self._bg_color = QColor(bg_color)
        self._border_color = QColor(border_color)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        w = self.width()
        h = self.height()

        # Border
        p.setPen(self._border_color)
        p.setBrush(self._bg_color)
        p.drawRect(0, 0, w - 1, h - 1)

        # Inner area (1px border inset)
        inner_x = 1
        inner_w = w - 2
        stripe_h = (h - 2) // 2  # 2 stripes in remaining height

        # Top stripe: time elapsed
        if self._time_pct > 0 and inner_w > 0:
            fill_w = int(inner_w * self._time_pct / 100)
            if fill_w > 0:
                p.fillRect(inner_x, 1, fill_w, stripe_h, self._time_color)

        # Bottom stripe: usage consumed
        top_of_bottom = 1 + stripe_h
        if self._usage_pct > 0 and inner_w > 0:
            fill_w = int(inner_w * self._usage_pct / 100)
            if fill_w > 0:
                p.fillRect(inner_x, top_of_bottom, fill_w, stripe_h, self._usage_color)

        p.end()
