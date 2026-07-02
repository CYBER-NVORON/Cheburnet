from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from cheburnet.app.ui.theme import COLORS
from cheburnet.app.ui.widgets.glass_card import GlassCard
from cheburnet.app.ui.widgets.log_console import LogConsole


class UpdateDial(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.status = "neutral"
        self.phase = 0.0
        self.setFixedSize(76, 76)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def set_status(self, status: str) -> None:
        self.status = status
        if status == "checking":
            self.timer.start(24)
        else:
            self.timer.stop()
        self.update()

    def _tick(self) -> None:
        self.phase = (self.phase + 0.022) % 1.0
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        color = QColor(self._color())
        color.setAlpha(40)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(center, 32, 32)

        ring = QColor(self._color())
        ring.setAlpha(170)
        painter.setPen(QPen(ring, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(8, 8, 60, 60)
        start = int((self.phase * 360 if self.status == "checking" else 35) * 16)
        span = 120 * 16 if self.status == "checking" else 290 * 16
        painter.drawArc(rect, start, span)

        if self.status == "checking":
            dot_angle = self.phase * math.tau
            dot = QPointF(center.x() + math.cos(dot_angle) * 31, center.y() + math.sin(dot_angle) * 31)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self._color()))
            painter.drawEllipse(dot, 4, 4)

        painter.setPen(QPen(QColor(self._color()), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        if self.status == "ok":
            painter.drawLine(QPointF(28, 39), QPointF(35, 46))
            painter.drawLine(QPointF(35, 46), QPointF(49, 29))
        elif self.status == "warn":
            painter.drawLine(QPointF(38, 24), QPointF(38, 43))
            painter.drawPoint(QPointF(38, 52))
        elif self.status == "error":
            painter.drawLine(QPointF(29, 29), QPointF(47, 47))
            painter.drawLine(QPointF(47, 29), QPointF(29, 47))
        elif self.status == "checking":
            painter.drawArc(QRectF(28, 28, 20, 20), int(self.phase * 360 * 16), 230 * 16)
        else:
            painter.drawLine(QPointF(28, 38), QPointF(48, 38))

    def _color(self) -> str:
        return {
            "ok": COLORS["accent2"],
            "warn": COLORS["warning"],
            "error": COLORS["danger"],
            "checking": COLORS["accent"],
        }.get(self.status, COLORS["muted"])


class UpdateCard(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("innerPanel")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(16)
        self.dial = UpdateDial()
        layout.addWidget(self.dial)
        text = QVBoxLayout()
        self.title = QLabel(title)
        self.title.setObjectName("updateTitle")
        self.version = QLabel("—")
        self.version.setObjectName("updateVersion")
        self.note = QLabel("Не проверялось")
        self.note.setObjectName("muted")
        self.note.setWordWrap(True)
        text.addWidget(self.title)
        text.addWidget(self.version)
        text.addWidget(self.note)
        layout.addLayout(text, 1)

    def set_state(self, status: str, version: str, note: str) -> None:
        self.dial.set_status(status)
        self.version.setText(version or "—")
        self.note.setText(note)


class UpdatesPage(QWidget):
    check_clicked = Signal()
    update_singbox_clicked = Signal()
    update_zapret_clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(18)

        card = GlassCard("Обновления")
        self.status_label = QLabel("Нажмите проверку версий")
        self.status_label.setObjectName("pageTitle")
        card.layout.addWidget(self.status_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        self.cards = {
            "app": UpdateCard("CheburNet"),
            "singbox": UpdateCard("sing-box"),
            "zapret": UpdateCard("Zapret"),
        }
        for index, widget in enumerate(self.cards.values()):
            grid.addWidget(widget, 0, index)
        card.layout.addLayout(grid)

        row = QHBoxLayout()
        for text, signal, primary in [
            ("Проверить", self.check_clicked, True),
            ("sing-box", self.update_singbox_clicked, False),
            ("Zapret", self.update_zapret_clicked, False),
        ]:
            button = QPushButton(text)
            if primary:
                button.setObjectName("primary")
            button.clicked.connect(lambda _checked=False, current_signal=signal: current_signal.emit())
            row.addWidget(button)
        row.addStretch(1)
        card.layout.addLayout(row)

        self.log = LogConsole()
        card.layout.addWidget(self.log)
        layout.addWidget(card)

    def set_checking(self) -> None:
        self.status_label.setText("Проверяю версии")
        for card in self.cards.values():
            card.set_state("checking", "…", "Запрос")

    def set_versions(self, data: dict[str, dict[str, Any]]) -> None:
        errors = 0
        warnings = 0
        for key, card in self.cards.items():
            item = data.get(key, {})
            status = str(item.get("status", "neutral"))
            if status == "error":
                errors += 1
            if status == "warn":
                warnings += 1
            card.set_state(status, str(item.get("version", "")), str(item.get("note", "")))
        if errors:
            self.status_label.setText("Есть ошибки проверки")
        elif warnings:
            self.status_label.setText("Есть доступные действия")
        else:
            self.status_label.setText("Всё актуально")

    def set_summary(self, text: str) -> None:
        self.status_label.setText(text.splitlines()[0] if text else "Проверка завершена")

    def append_log(self, line: str) -> None:
        self.log.append_line(line)
