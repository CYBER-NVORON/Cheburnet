from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from cheburnet.app.ui.widgets.glass_card import GlassCard


class RulesPage(QWidget):
    save_clicked = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        card = GlassCard("Правила маршрутизации")
        note = QLabel("Домены из списка идут напрямую. В Smart split YouTube/Discord добавляются автоматически для Zapret.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        card.layout.addWidget(note)
        self.editor = QTextEdit()
        self.editor.setPlaceholderText(".ru\n.рф\n.su\nvk.com")
        card.layout.addWidget(self.editor)
        save = QPushButton("Сохранить правила")
        save.setObjectName("primary")
        save.clicked.connect(lambda _checked=False: self._save())
        card.layout.addWidget(save)
        layout.addWidget(card)

    def set_domains(self, domains: list[str]) -> None:
        self.editor.setPlainText("\n".join(domains))

    def _save(self) -> None:
        domains = [line.strip() for line in self.editor.toPlainText().splitlines() if line.strip()]
        self.save_clicked.emit(domains)
