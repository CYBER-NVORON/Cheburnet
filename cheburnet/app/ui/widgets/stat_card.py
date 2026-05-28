from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class StatCard(QFrame):
    def __init__(self, label: str, value: str = "-") -> None:
        super().__init__()
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        self.label = QLabel(label)
        self.label.setObjectName("muted")
        self.value = QLabel(value)
        self.value.setObjectName("metric")
        layout.addWidget(self.label)
        layout.addWidget(self.value)
