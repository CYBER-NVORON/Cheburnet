from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from cheburnet.app.app_state import AppState
from cheburnet.app.ui.widgets.glass_card import GlassCard
from cheburnet.app.ui.widgets.log_console import LogConsole


class LogsPage(QWidget):
    clear_clicked = Signal()

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        card = GlassCard("Журнал")
        row = QHBoxLayout()
        clear = QPushButton("Очистить")
        clear.clicked.connect(lambda _checked=False: self.clear_clicked.emit())
        row.addWidget(clear)
        row.addStretch(1)
        card.layout.addLayout(row)
        self.console = LogConsole()
        card.layout.addWidget(self.console)
        layout.addWidget(card)
        state.log_added.connect(self.console.append_line)
