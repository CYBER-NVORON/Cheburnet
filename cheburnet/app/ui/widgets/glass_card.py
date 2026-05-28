from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class GlassCard(QFrame):
    def __init__(self, title: str = "") -> None:
        super().__init__()
        self.setObjectName("glassCard")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(22, 20, 22, 20)
        self.layout.setSpacing(14)
        if title:
            label = QLabel(title)
            label.setObjectName("cardTitle")
            self.layout.addWidget(label)
