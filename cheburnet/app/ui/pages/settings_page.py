from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from cheburnet.app.ui.widgets.glass_card import GlassCard


class SettingsPage(QWidget):
    save_clicked = Signal(dict)
    open_data_clicked = Signal()
    open_log_clicked = Signal()
    reset_clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        card = GlassCard("Настройки")
        form = QFormLayout()
        form.setSpacing(14)
        self.routing_mode = QComboBox()
        self.routing_mode.addItem("Обычный VPN", "full_vpn")
        self.routing_mode.addItem("Туннелирование", "smart_split")
        self.routing_mode.addItem("Выключен", "zapret_only")
        self.zapret_mode = QComboBox()
        self.zapret_mode.addItem("Авто", "auto")
        self.zapret_mode.addItem("Вручную", "manual")
        self.auto_connect = QCheckBox("Автоподключение при запуске")
        self.auto_failover = QCheckBox("Если VPN-конфиг не работает, переключаться на другой")
        self.dns_protection = QCheckBox("DNS protection")
        self.kill_switch = QCheckBox("Kill switch")
        self.zapret_autostart = QCheckBox("Автозапуск Zapret")
        self.free_auto = QCheckBox("Автообновление пользовательских списков")
        self.sources = QTextEdit()
        self.sources.setPlaceholderText("https://example.com/profiles.txt")
        self.sources.setMaximumHeight(110)
        self.sources_label = QLabel("URL списков профилей, по одной ссылке на строку")
        self.sources_label.setObjectName("muted")
        for label, widget in [
            ("Режим", self.routing_mode),
            ("Zapret mode", self.zapret_mode),
            ("VPN", self.auto_connect),
            ("Failover", self.auto_failover),
            ("DNS", self.dns_protection),
            ("Kill switch", self.kill_switch),
            ("Zapret", self.zapret_autostart),
            ("Списки профилей", self.free_auto),
        ]:
            form.addRow(label, widget)
        card.layout.addLayout(form)
        card.layout.addWidget(self.sources_label)
        card.layout.addWidget(self.sources)
        save = QPushButton("Сохранить")
        save.setObjectName("primary")
        save.clicked.connect(lambda _checked=False: self._save())
        card.layout.addWidget(save)
        for text, signal in [
            ("Открыть папку данных", self.open_data_clicked),
            ("Открыть журнал", self.open_log_clicked),
            ("Сбросить настройки", self.reset_clicked),
        ]:
            button = QPushButton(text)
            button.clicked.connect(lambda _checked=False, current_signal=signal: current_signal.emit())
            card.layout.addWidget(button)
        layout.addWidget(card)
        layout.addStretch(1)

    def set_values(self, settings: dict) -> None:
        self._set_combo_data(self.routing_mode, str(settings.get("routing_mode", "full_vpn")))
        vpn = settings.get("vpn", {})
        zapret = settings.get("zapret", {})
        free = settings.get("free_configs", {})
        self.auto_connect.setChecked(bool(vpn.get("auto_connect", False)))
        self.auto_failover.setChecked(bool(vpn.get("auto_failover", False)))
        self.dns_protection.setChecked(bool(vpn.get("dns_protection", True)))
        self.kill_switch.setChecked(bool(vpn.get("kill_switch", False)))
        self._set_combo_data(self.zapret_mode, str(zapret.get("mode", "auto")))
        self.zapret_autostart.setChecked(bool(zapret.get("autostart_with_app", False)))
        self.free_auto.setChecked(bool(free.get("auto_update", False)))
        self.sources.setPlainText("\n".join(str(item) for item in free.get("sources", [])))

    def _save(self) -> None:
        self.save_clicked.emit(
            {
                "routing_mode": self.routing_mode.currentData() or "full_vpn",
                "vpn": {
                    "auto_connect": self.auto_connect.isChecked(),
                    "auto_failover": self.auto_failover.isChecked(),
                    "dns_protection": self.dns_protection.isChecked(),
                    "kill_switch": self.kill_switch.isChecked(),
                },
                "zapret": {"mode": self.zapret_mode.currentData() or "auto", "autostart_with_app": self.zapret_autostart.isChecked()},
                "free_configs": {
                    "auto_update": self.free_auto.isChecked(),
                    "sources": [line.strip() for line in self.sources.toPlainText().splitlines() if line.strip()],
                },
            }
        )

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
