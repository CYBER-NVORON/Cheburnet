from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cheburnet.app.app_state import AppState
from cheburnet.app.models.health import HealthCheckResult, HealthStatus
from cheburnet.app.models.zapret_status import ZapretStatus
from cheburnet.app.ui.widgets.glass_card import GlassCard
from cheburnet.app.ui.widgets.status_pill import StatusPill


class ZapretPage(QWidget):
    download_clicked = Signal()
    start_clicked = Signal()
    stop_clicked = Signal()
    open_folder_clicked = Signal()
    choose_folder_clicked = Signal()
    check_services_clicked = Signal()
    test_all_clicked = Signal()
    stop_test_clicked = Signal()
    mode_changed = Signal(str)
    script_changed = Signal(str)
    options_changed = Signal(dict)

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        self.scripts: list[Path] = []
        self.setObjectName("page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(18)

        card = GlassCard("Zapret")
        top = QHBoxLayout()
        self.status = QLabel("Zapret не установлен")
        self.status.setObjectName("pageTitle")
        self.pill = StatusPill("Не установлен", "warn")
        top.addWidget(self.status)
        top.addWidget(self.pill)
        top.addStretch(1)
        card.layout.addLayout(top)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Авто подбор", "auto")
        self.mode_combo.addItem("Выбранный конфиг", "manual")
        self.mode_combo.currentIndexChanged.connect(lambda _index: self.mode_changed.emit(self.mode()))
        card.layout.addWidget(self.mode_combo)

        self.script_combo = QComboBox()
        self.script_combo.currentIndexChanged.connect(self._emit_script_changed)
        card.layout.addWidget(self.script_combo)

        options = QHBoxLayout()
        self.game_filter = QComboBox()
        self.game_filter.addItem("Game filter: выключен", "off")
        self.game_filter.addItem("Game filter: TCP", "tcp")
        self.game_filter.addItem("Game filter: UDP", "udp")
        self.game_filter.addItem("Game filter: TCP + UDP", "all")
        self.ipset_filter = QCheckBox("IPSet filter")
        self.update_check = QCheckBox("Auto-update check")
        save_options = QPushButton("Сохранить фильтры")
        save_options.clicked.connect(lambda _checked=False: self.options_changed.emit(self.options()))
        options.addWidget(self.game_filter)
        options.addWidget(self.ipset_filter)
        options.addWidget(self.update_check)
        options.addWidget(save_options)
        options.addStretch(1)
        card.layout.addLayout(options)

        health_row = QHBoxLayout()
        self.youtube_pill = StatusPill("YouTube: не проверялось", "neutral")
        self.discord_pill = StatusPill("Discord: не проверялось", "neutral")
        health_row.addWidget(self.youtube_pill)
        health_row.addWidget(self.discord_pill)
        health_row.addStretch(1)
        card.layout.addLayout(health_row)

        buttons = QHBoxLayout()
        for text, signal, obj in [
            ("Скачать / обновить", self.download_clicked, "primary"),
            ("Включить", self.start_clicked, "primary"),
            ("Выключить", self.stop_clicked, "danger"),
            ("Выбрать папку", self.choose_folder_clicked, ""),
            ("Открыть папку", self.open_folder_clicked, ""),
        ]:
            button = QPushButton(text)
            button.setMinimumWidth(150)
            if obj:
                button.setObjectName(obj)
            button.clicked.connect(lambda _checked=False, current_signal=signal: current_signal.emit())
            buttons.addWidget(button)
        card.layout.addLayout(buttons)

        checks = QHBoxLayout()
        check = QPushButton("Проверить YouTube/Discord")
        check.clicked.connect(lambda _checked=False: self.check_services_clicked.emit())
        test_all = QPushButton("Тест всех конфигов")
        test_all.clicked.connect(lambda _checked=False: self.test_all_clicked.emit())
        stop_test = QPushButton("Остановить тест")
        stop_test.setObjectName("danger")
        stop_test.clicked.connect(lambda _checked=False: self.stop_test_clicked.emit())
        checks.addWidget(check)
        checks.addWidget(test_all)
        checks.addWidget(stop_test)
        checks.addStretch(1)
        card.layout.addLayout(checks)
        layout.addWidget(card)

        results = GlassCard("Результаты теста конфигов")
        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(["Конфиг", "YouTube", "Discord", "Score", "Детали"])
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setShowGrid(False)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        results.layout.addWidget(self.results_table)
        layout.addWidget(results, 1)

        state.zapret_status_changed.connect(self.set_status)
        state.health_changed.connect(self.set_health)
        self.set_status(state.zapret_status)

    def set_scripts(self, scripts: list[Path], selected: str = "") -> None:
        self.scripts = scripts
        self.script_combo.blockSignals(True)
        self.script_combo.clear()
        for script in scripts:
            self.script_combo.addItem(script.name, str(script))
        if selected:
            self.set_selected_script(selected)
        self.script_combo.blockSignals(False)

    def selected_script(self) -> Path | None:
        data = self.script_combo.currentData()
        return Path(str(data)) if data else None

    def mode(self) -> str:
        return str(self.mode_combo.currentData() or "auto")

    def set_mode(self, mode: str) -> None:
        index = self.mode_combo.findData(mode if mode in {"auto", "manual"} else "auto")
        if index >= 0:
            self.mode_combo.setCurrentIndex(index)

    def set_selected_script(self, value: str) -> None:
        for index in range(self.script_combo.count()):
            data = str(self.script_combo.itemData(index))
            if data == value or Path(data).name == value:
                self.script_combo.setCurrentIndex(index)
                return

    def options(self) -> dict[str, object]:
        return {
            "game_filter": self.game_filter.currentData() or "off",
            "ipset_filter": self.ipset_filter.isChecked(),
            "update_check": self.update_check.isChecked(),
        }

    def set_options(self, values: dict[str, object]) -> None:
        index = self.game_filter.findData(str(values.get("game_filter", "off")))
        if index >= 0:
            self.game_filter.setCurrentIndex(index)
        self.ipset_filter.setChecked(bool(values.get("ipset_filter", False)))
        self.update_check.setChecked(bool(values.get("update_check", False)))

    def set_test_results(self, rows: list[dict[str, object]]) -> None:
        self.results_table.setRowCount(0)
        for row in rows:
            self.append_test_result(row)
        self.results_table.resizeColumnsToContents()

    def append_test_result(self, row: dict[str, object]) -> None:
        index = self.results_table.rowCount()
        self.results_table.insertRow(index)
        values = [
            str(row.get("script", "")),
            str(row.get("youtube", "")),
            str(row.get("discord", "")),
            str(row.get("score", "")),
            str(row.get("detail", "")),
        ]
        for column, value in enumerate(values):
            self.results_table.setItem(index, column, QTableWidgetItem(value))
        self.results_table.resizeColumnsToContents()

    def set_status(self, status: ZapretStatus) -> None:
        if status == ZapretStatus.RUNNING:
            self.status.setText("Zapret включен")
            self.pill.set_status("ok", "Работает")
        elif status in {ZapretStatus.STARTING, ZapretStatus.STOPPING}:
            self.status.setText("Zapret выполняет действие")
            self.pill.set_status("warn", "Подождите")
        elif status == ZapretStatus.ERROR:
            self.status.setText("Ошибка Zapret")
            self.pill.set_status("error", "Ошибка")
        elif status == ZapretStatus.NOT_INSTALLED:
            self.status.setText("Zapret не установлен")
            self.pill.set_status("warn", "Не установлен")
        else:
            self.status.setText("Zapret выключен")
            self.pill.set_status("neutral", "Остановлен")

    def set_health(self, service: str, result: HealthCheckResult) -> None:
        if service not in {"youtube", "discord"}:
            return
        text = {
            HealthStatus.UNCHECKED: "не проверялось",
            HealthStatus.CHECKING: "проверяется...",
            HealthStatus.OK: "работает",
            HealthStatus.FAILED: "не работает",
            HealthStatus.TIMEOUT: "таймаут",
        }[result.status]
        status = "ok" if result.status == HealthStatus.OK else "warn" if result.status in {HealthStatus.UNCHECKED, HealthStatus.CHECKING} else "error"
        label = self.youtube_pill if service == "youtube" else self.discord_pill
        label.set_status(status, f"{service.title()}: {text}")

    def _emit_script_changed(self, _index: int) -> None:
        data = self.script_combo.currentData()
        if data:
            self.script_changed.emit(str(data))
