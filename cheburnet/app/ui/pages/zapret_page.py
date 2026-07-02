from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cheburnet.app.app_state import AppState
from cheburnet.app.models.health import HealthCheckResult, HealthStatus
from cheburnet.app.models.zapret_status import ZapretStatus
from cheburnet.app.ui.theme import COLORS
from cheburnet.app.ui.widgets.flow_layout import FlowLayout
from cheburnet.app.ui.widgets.glass_card import GlassCard
from cheburnet.app.ui.widgets.status_pill import StatusPill


class SnakeProgress(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.phase = 0.0
        self.velocity = 0.018
        self.setMinimumHeight(34)
        self.setMaximumHeight(34)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def set_running(self, running: bool) -> None:
        self.setVisible(running)
        if running:
            self.phase = 0.0
            self.velocity = 0.018
            self.timer.start(22)
        else:
            self.timer.stop()
        self.update()

    def _tick(self) -> None:
        wave = (math.sin(self.phase * math.tau * 1.7) + 1.0) / 2.0
        self.velocity = 0.010 + wave * 0.026
        self.phase = (self.phase + self.velocity) % 1.0
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 8, -2, -8)
        track = QColor(COLORS["input"])
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.setBrush(track)
        painter.drawRoundedRect(rect, 9, 9)

        width = max(1, rect.width())
        segment_count = 13
        step = width / segment_count
        head_x = rect.left() + self.phase * width
        for index in range(segment_count):
            offset = index * step * 0.72
            x = rect.left() + ((head_x - rect.left() - offset) % width)
            body_phase = index / max(1, segment_count - 1)
            alpha = int(235 - body_phase * 165)
            radius = 5.8 - body_phase * 2.0
            y = rect.center().y() + math.sin((self.phase * 5.0 - body_phase * 2.5) * math.tau) * 2.8
            color = QColor(COLORS["accent2"] if index < 3 else COLORS["accent"])
            color.setAlpha(max(70, alpha))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(x, y), radius, radius)

        head = QColor(COLORS["accent2"])
        painter.setBrush(head)
        painter.drawEllipse(QPointF(head_x, rect.center().y()), 7, 7)
        painter.setPen(QPen(QColor(COLORS["bg"]), 1.5))
        painter.drawPoint(QPointF(head_x + 2.4, rect.center().y() - 2.0))


class ZapretPage(QWidget):
    download_clicked = Signal()
    start_clicked = Signal()
    stop_clicked = Signal()
    choose_folder_clicked = Signal()
    update_ipset_clicked = Signal()
    update_hosts_clicked = Signal()
    diagnostics_clicked = Signal()
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
        self.status.setWordWrap(True)
        self.pill = StatusPill("Не установлен", "warn")
        top.addWidget(self.status)
        top.addWidget(self.pill)
        top.addStretch(1)
        card.layout.addLayout(top)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Авто: подобрать рабочий", "auto")
        self.mode_combo.addItem("Выбранный .bat", "manual")
        self.mode_combo.setToolTip("Авто пробует .bat по очереди. Выбранный .bat запускает только текущий конфиг.")
        self.mode_combo.currentIndexChanged.connect(self._emit_mode_changed)
        card.layout.addWidget(self.mode_combo)

        self.script_combo = QComboBox()
        self.script_combo.setToolTip("Конфиг Flowseal, который будет запускаться в режиме выбранного .bat.")
        self.script_combo.currentIndexChanged.connect(self._emit_script_changed)
        card.layout.addWidget(self.script_combo)

        options = FlowLayout(spacing=10)
        self.game_filter = QComboBox()
        self.game_filter.addItem("Game filter: выключен", "off")
        self.game_filter.addItem("Game filter: TCP", "tcp")
        self.game_filter.addItem("Game filter: UDP", "udp")
        self.game_filter.addItem("Game filter: TCP + UDP", "all")
        self.ipset_filter = QCheckBox("IPSet filter")
        save_options = QPushButton("Сохранить фильтры")
        save_options.clicked.connect(lambda _checked=False: self.options_changed.emit(self.options()))
        options.addWidget(self.game_filter)
        options.addWidget(self.ipset_filter)
        options.addWidget(save_options)
        card.layout.addLayout(options)

        health_row = FlowLayout(spacing=10)
        self.youtube_pill = StatusPill("YouTube: не проверялось", "neutral")
        self.discord_pill = StatusPill("Discord: не проверялось", "neutral")
        health_row.addWidget(self.youtube_pill)
        health_row.addWidget(self.discord_pill)
        card.layout.addLayout(health_row)

        buttons = FlowLayout(spacing=12)
        for text, signal, obj in [
            ("Скачать / обновить", self.download_clicked, "primary"),
            ("Включить", self.start_clicked, "primary"),
            ("Выключить", self.stop_clicked, "danger"),
            ("Папка", self.choose_folder_clicked, ""),
        ]:
            button = QPushButton(text)
            button.setMinimumWidth(118)
            if obj:
                button.setObjectName(obj)
            button.clicked.connect(lambda _checked=False, current_signal=signal: current_signal.emit())
            buttons.addWidget(button)
        card.layout.addLayout(buttons)

        checks = FlowLayout(spacing=12)
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
        card.layout.addLayout(checks)

        self.advanced_toggle = QToolButton()
        self.advanced_toggle.setText("Дополнительно")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.advanced_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.advanced_toggle.toggled.connect(self._set_advanced_visible)
        card.layout.addWidget(self.advanced_toggle)

        self.advanced_panel = QWidget()
        service_grid = QGridLayout(self.advanced_panel)
        service_grid.setContentsMargins(0, 0, 0, 0)
        service_grid.setHorizontalSpacing(12)
        service_grid.setVerticalSpacing(10)
        service_actions = [
            ("Обновить IPSet", self.update_ipset_clicked),
            ("Обновить hosts", self.update_hosts_clicked),
            ("Диагностика", self.diagnostics_clicked),
        ]
        for index, (text, signal) in enumerate(service_actions):
            button = QPushButton(text)
            button.setMinimumWidth(150)
            button.clicked.connect(lambda _checked=False, current_signal=signal: current_signal.emit())
            service_grid.addWidget(button, index // 2, index % 2)
        self.advanced_panel.setVisible(False)
        card.layout.addWidget(self.advanced_panel)
        layout.addWidget(card)

        results = GlassCard("Результаты теста конфигов")
        self.test_progress = SnakeProgress()
        self.test_progress.set_running(False)
        results.layout.addWidget(self.test_progress)
        self.test_status = QLabel("Проверка конфигов...")
        self.test_status.setObjectName("muted")
        self.test_status.setVisible(False)
        results.layout.addWidget(self.test_status)
        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["Конфиг", "YouTube", "Discord", "Итог"])
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setShowGrid(False)
        self.results_table.verticalHeader().setVisible(False)
        header = self.results_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        self.results_table.setColumnWidth(1, 90)
        self.results_table.setColumnWidth(2, 90)
        self.results_table.setColumnWidth(3, 130)
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
        self._update_script_enabled()

    def selected_script(self) -> Path | None:
        data = self.script_combo.currentData()
        return Path(str(data)) if data else None

    def mode(self) -> str:
        return str(self.mode_combo.currentData() or "auto")

    def set_mode(self, mode: str) -> None:
        index = self.mode_combo.findData(mode if mode in {"auto", "manual"} else "auto")
        if index >= 0:
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentIndex(index)
            self.mode_combo.blockSignals(False)
        self._update_script_enabled()

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
        }

    def set_options(self, values: dict[str, object]) -> None:
        index = self.game_filter.findData(str(values.get("game_filter", "off")))
        if index >= 0:
            self.game_filter.setCurrentIndex(index)
        self.ipset_filter.setChecked(bool(values.get("ipset_filter", False)))

    def set_test_results(self, rows: list[dict[str, object]]) -> None:
        self.results_table.setUpdatesEnabled(False)
        self.results_table.setRowCount(0)
        try:
            for row in rows:
                self.append_test_result(row)
        finally:
            self.results_table.setUpdatesEnabled(True)

    def append_test_result(self, row: dict[str, object]) -> None:
        index = self.results_table.rowCount()
        self.results_table.insertRow(index)
        detail = str(row.get("detail", ""))
        total = int(row.get("total", 8) or 8)
        score = int(row.get("score", 0) or 0)
        result_text, color = self._result_label(score, total)
        values = [
            str(row.get("script", "")),
            str(row.get("youtube", "")),
            str(row.get("discord", "")),
            result_text,
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setToolTip(detail)
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignLeft if column == 0 else Qt.AlignmentFlag.AlignCenter))
            if column == 3:
                item.setForeground(QColor(color))
            self.results_table.setItem(index, column, item)

    def set_test_running(self, running: bool) -> None:
        self.test_progress.set_running(running)
        self.test_status.setVisible(running)

    @staticmethod
    def _result_label(score: int, total: int) -> tuple[str, str]:
        if total > 0 and score >= total:
            return "Подходит", COLORS["accent2"]
        if score > 0:
            return "Частично", COLORS["warning"]
        return "Не подошёл", COLORS["danger"]

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

    def _emit_mode_changed(self, _index: int) -> None:
        self._update_script_enabled()
        self.mode_changed.emit(self.mode())

    def _update_script_enabled(self) -> None:
        self.script_combo.setEnabled(self.mode() == "manual")

    def _set_advanced_visible(self, visible: bool) -> None:
        self.advanced_panel.setVisible(visible)
        self.advanced_toggle.setArrowType(Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow)

    def _emit_script_changed(self, _index: int) -> None:
        data = self.script_combo.currentData()
        if data:
            self.script_changed.emit(str(data))
