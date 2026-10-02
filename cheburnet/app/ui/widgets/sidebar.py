from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from cheburnet.app.constants import APP_NAME


class Sidebar(QFrame):
    page_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("sidebar")
        self.setFixedWidth(240)
        self.buttons: dict[str, QPushButton] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 20, 18, 20)
        layout.setSpacing(12)

        brand_row = QHBoxLayout()
        logo = QLabel("◈")
        logo.setObjectName("metric")
        brand = QLabel(APP_NAME)
        brand.setObjectName("brand")
        brand_row.addWidget(logo)
        brand_row.addWidget(brand, 1)
        layout.addLayout(brand_row)
        layout.addSpacing(18)

        for key, text, tooltip in [
            ("dashboard", "Главная (Статус)", "Общая информация и быстрый запуск"),
            ("vpn", "VPN и серверы", "Настройка VPN подключений и прокси"),
            ("zapret", "Zapret", "Управление сервисом Zapret (YouTube/Discord)"),
            ("rules", "Правила (Сплит)", "Настройка туннелирования и разделения трафика"),
            ("logs", "Журнал (Логи)", "Просмотр логов работы программы"),
            ("settings", "Настройки", "Общие настройки интерфейса и поведения"),
            ("updates", "Обновления", "Проверка новых версий CheburNet и компонентов"),
        ]:
            button = QPushButton(text)
            button.setObjectName("navButton")
            button.setToolTip(tooltip)
            button.clicked.connect(lambda _checked=False, page=key: self.page_selected.emit(page))
            layout.addWidget(button)
            self.buttons[key] = button

        layout.addStretch(1)
        self.traffic = QLabel("↓ 0.0 Mbps\n↑ 0.0 Mbps")
        self.traffic.setObjectName("metric")
        layout.addWidget(self.traffic)

    def set_active(self, key: str) -> None:
        for page, button in self.buttons.items():
            button.setProperty("active", page == key)
            button.style().unpolish(button)
            button.style().polish(button)

    def set_admin(self, admin: bool) -> None:
        return None

    def set_traffic(self, down: float, up: float) -> None:
        self.traffic.setText(f"↓ {down:.1f} Mbps\n↑ {up:.1f} Mbps")
