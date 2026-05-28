from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from cheburnet.app.ui.widgets.glass_card import GlassCard
from cheburnet.app.ui.widgets.log_console import LogConsole


class UpdatesPage(QWidget):
    check_clicked = Signal()
    update_singbox_clicked = Signal()
    update_zapret_clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        card = GlassCard("Обновления")
        self.summary = QLabel("Версии будут показаны после проверки.")
        self.summary.setObjectName("muted")
        card.layout.addWidget(self.summary)
        row = QHBoxLayout()
        for text, signal, primary in [
            ("Проверить версии", self.check_clicked, True),
            ("Обновить sing-box", self.update_singbox_clicked, False),
            ("Обновить Zapret", self.update_zapret_clicked, False),
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

    def set_summary(self, text: str) -> None:
        self.summary.setText(text)

    def append_log(self, line: str) -> None:
        self.log.append_line(line)
