from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from cheburnet.app.ui.theme import COLORS


class PowerButton(QWidget):
    clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.active = False
        self.busy = False
        self.phase = 0.0
        self.setFixedSize(238, 238)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

    def set_active(self, value: bool) -> None:
        self.active = value
        self.update()

    def set_busy(self, value: bool) -> None:
        self.busy = value
        self.update()

    def mousePressEvent(self, _event) -> None:  # type: ignore[override]
        self.clicked.emit()

    def _tick(self) -> None:
        self.phase = (self.phase + 0.018) % 1.0
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        pulse = 0.5 + 0.5 * math.sin(self.phase * math.tau)
        accent = QColor(COLORS["accent2"] if self.active else COLORS["accent"])
        if self.busy:
            accent = QColor(COLORS["warning"])
        for index in range(3):
            radius = 74 + index * 18 + pulse * (9 if self.active or self.busy else 4)
            color = QColor(accent)
            color.setAlpha(120 - index * 30)
            painter.setPen(QPen(color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius, radius)

        glow = QColor(accent)
        glow.setAlpha(42 if self.active else 26)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(center, 77 + pulse * 4, 77 + pulse * 4)

        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.setBrush(QColor(COLORS["input"]))
        painter.drawEllipse(center, 68, 68)

        painter.setPen(QPen(QColor(COLORS["text"]), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        arc = QRectF(center.x() - 34, center.y() - 34, 68, 68)
        painter.drawArc(arc, 125 * 16, 290 * 16)
        painter.drawLine(QPointF(center.x(), center.y() - 42), QPointF(center.x(), center.y() - 9))
