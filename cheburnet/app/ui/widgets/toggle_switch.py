from __future__ import annotations

from PySide6.QtWidgets import QPushButton


class ToggleSwitch(QPushButton):
    def __init__(self, checked_text: str = "Включен", unchecked_text: str = "Выключен") -> None:
        super().__init__()
        self.checked_text = checked_text
        self.unchecked_text = unchecked_text
        self.setCheckable(True)
        self.toggled.connect(self._render)
        self._render(False)

    def _render(self, checked: bool) -> None:
        self.setText(self.checked_text if checked else self.unchecked_text)
        self.setObjectName("primary" if checked else "")
        self.style().unpolish(self)
        self.style().polish(self)
