from __future__ import annotations

from PySide6.QtWidgets import QLabel


class StatusPill(QLabel):
    def __init__(self, text: str = "", status: str = "neutral") -> None:
        super().__init__(text)
        self.setObjectName("statusPill")
        self.set_status(status, text)

    def set_status(self, status: str, text: str | None = None) -> None:
        if text is not None:
            self.setText(text)
        self.setProperty("status", status)
        self.style().unpolish(self)
        self.style().polish(self)
