from __future__ import annotations

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextEdit


class LogConsole(QTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("logConsole")
        self.setReadOnly(True)
        self.setPlaceholderText("События появятся здесь.")

    def append_line(self, line: str) -> None:
        self.append(line)
        self.moveCursor(QTextCursor.MoveOperation.End)
