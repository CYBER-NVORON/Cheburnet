from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from cheburnet.app.app_state import AppState
from cheburnet.app.models.health import HealthCheckResult, HealthStatus
from cheburnet.app.models.profile import Profile
from cheburnet.app.models.vpn_status import VpnStatus
from cheburnet.app.models.zapret_status import ZapretStatus
from cheburnet.app.ui.widgets.glass_card import GlassCard
from cheburnet.app.ui.widgets.power_button import PowerButton
from cheburnet.app.ui.widgets.stat_card import StatCard
from cheburnet.app.ui.widgets.status_pill import StatusPill


class DashboardPage(QWidget):
    power_clicked = Signal()
    zapret_clicked = Signal()
    import_wireguard_clicked = Signal()
    server_selected = Signal(str)
    routing_mode_changed = Signal(str)

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        self.setObjectName("page")
        self._build()
        self._connect_state()
        self.set_vpn_status(self.state.vpn_status)
        self.set_zapret_status(self.state.zapret_status)
        self.set_profile(self.state.selected_profile)
        self.set_routes(self.state.routes)
        self.render_servers(self.state.servers)

    def _build(self) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(18)
        layout.setColumnStretch(0, 2)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)

        self.vpn_card = GlassCard()
        top = QHBoxLayout()
        left = QVBoxLayout()
        status_row = QHBoxLayout()
        self.vpn_status = QLabel("VPN отключен")
        self.vpn_status.setObjectName("bigStatus")
        self.vpn_status.setWordWrap(True)
        self.vpn_pill = StatusPill("Не защищено", "warn")
        status_row.addWidget(self.vpn_status)
        status_row.addWidget(self.vpn_pill)
        status_row.addStretch(1)
        left.addLayout(status_row)
        self.profile_title = QLabel("Сервер не выбран")
        self.profile_title.setObjectName("pageTitle")
        self.profile_title.setWordWrap(True)
        left.addWidget(self.profile_title)
        self.profile_detail = QLabel("Добавьте ссылку профиля или WireGuard .conf во вкладке VPN.")
        self.profile_detail.setObjectName("muted")
        self.profile_detail.setWordWrap(True)
        left.addWidget(self.profile_detail)
        self.routing_mode = QComboBox()
        self.routing_mode.addItem("Обычный VPN", "full_vpn")
        self.routing_mode.addItem("Туннелирование", "smart_split")
        self.routing_mode.addItem("Выключен", "zapret_only")
        self.routing_mode.currentIndexChanged.connect(lambda _index: self.routing_mode_changed.emit(str(self.routing_mode.currentData() or "full_vpn")))
        left.addWidget(self.routing_mode)
        metrics = QHBoxLayout()
        self.ping = StatCard("Пинг", "-")
        self.protocol = StatCard("Протокол", "-")
        for widget in (self.ping, self.protocol):
            metrics.addWidget(widget)
        metrics.addStretch(1)
        left.addLayout(metrics)
        left.addStretch(1)
        top.addLayout(left, 1)
        self.power = PowerButton()
        self.power.clicked.connect(self.power_clicked.emit)
        top.addWidget(self.power)
        self.vpn_card.layout.addLayout(top)
        layout.addWidget(self.vpn_card, 0, 0, 1, 2)

        zapret = GlassCard("Zapret")
        ztop = QHBoxLayout()
        self.zapret_pill = StatusPill("Не установлен", "warn")
        self.zapret_button = QPushButton("Скачать Zapret")
        self.zapret_button.setObjectName("primary")
        self.zapret_button.clicked.connect(lambda _checked=False: self.zapret_clicked.emit())
        ztop.addWidget(self.zapret_pill)
        ztop.addStretch(1)
        ztop.addWidget(self.zapret_button)
        zapret.layout.addLayout(ztop)
        self.health_pills: dict[str, StatusPill] = {}
        for key, name in (("youtube", "YouTube"), ("discord", "Discord"), ("other", "Другие сайты")):
            row = QHBoxLayout()
            row.addWidget(QLabel(name))
            row.addStretch(1)
            pill = StatusPill("Не проверялось" if key != "other" else "По режиму", "neutral")
            row.addWidget(pill)
            self.health_pills[key] = pill
            zapret.layout.addLayout(row)
        layout.addWidget(zapret, 0, 2)

        servers = GlassCard("Серверы")
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск серверов...")
        self.search.textChanged.connect(lambda _text: self.render_servers(self.state.servers))
        self.protocol_filter = QComboBox()
        self.protocol_filter.addItems(["Все", "VLESS", "VMess", "Trojan", "SS", "Hysteria2", "WireGuard"])
        self.protocol_filter.currentTextChanged.connect(lambda _text: self.render_servers(self.state.servers))
        row.addWidget(self.search, 1)
        row.addWidget(self.protocol_filter)
        servers.layout.addLayout(row)
        self.server_tree = QTreeWidget()
        self.server_tree.setColumnCount(4)
        self.server_tree.setHeaderLabels(["Название", "Протокол", "Пинг", "Статус"])
        self.server_tree.setUniformRowHeights(True)
        self.server_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        for column, width in enumerate((520, 120, 90, 140)):
            self.server_tree.setColumnWidth(column, width)
        self.server_tree.itemSelectionChanged.connect(self._emit_selected)
        servers.layout.addWidget(self.server_tree)
        layout.addWidget(servers, 1, 0, 1, 3)

    def _connect_state(self) -> None:
        self.state.vpn_status_changed.connect(self.set_vpn_status)
        self.state.zapret_status_changed.connect(self.set_zapret_status)
        self.state.servers_changed.connect(self.render_servers)
        self.state.selected_profile_changed.connect(self.set_profile)
        self.state.health_changed.connect(self.set_health)
        self.state.routes_changed.connect(self.set_routes)

    def set_routing_mode(self, mode: str) -> None:
        value = mode if mode in {"full_vpn", "smart_split", "zapret_only"} else "full_vpn"
        index = self.routing_mode.findData(value)
        if index >= 0 and self.routing_mode.currentIndex() != index:
            self.routing_mode.blockSignals(True)
            self.routing_mode.setCurrentIndex(index)
            self.routing_mode.blockSignals(False)

    def set_vpn_status(self, status: VpnStatus) -> None:
        connected = status == VpnStatus.CONNECTED
        busy = status in {VpnStatus.CONNECTING, VpnStatus.DISCONNECTING}
        self.power.set_active(connected)
        self.power.set_busy(busy)
        self.vpn_status.setText("VPN подключен" if connected else "VPN отключен" if status != VpnStatus.ERROR else "Ошибка VPN")
        self.vpn_pill.set_status("ok" if connected else "error" if status == VpnStatus.ERROR else "warn", "Защищено" if connected else "Не защищено")

    def set_zapret_status(self, status: ZapretStatus) -> None:
        if status == ZapretStatus.RUNNING:
            self.zapret_pill.set_status("ok", "Включен")
            self.zapret_button.setText("Выключить")
        elif status == ZapretStatus.NOT_INSTALLED:
            self.zapret_pill.set_status("warn", "Не установлен")
            self.zapret_button.setText("Скачать")
        elif status == ZapretStatus.ERROR:
            self.zapret_pill.set_status("error", "Ошибка")
            self.zapret_button.setText("Переустановить")
        else:
            self.zapret_pill.set_status("neutral", "Выключен")
            self.zapret_button.setText("Включить")

    def set_routes(self, routes: dict[str, str]) -> None:
        other = routes.get("other") or "по режиму"
        self.health_pills["other"].set_status("neutral", other)

    def set_profile(self, profile: Profile | None) -> None:
        if not profile:
            self.profile_title.setText("Сервер не выбран")
            self.profile_detail.setText("Добавьте ссылку профиля или WireGuard .conf во вкладке VPN.")
            self.ping.value.setText("-")
            self.protocol.value.setText("-")
            return
        self.profile_title.setText(profile.name)
        self.profile_detail.setText(f"{profile.protocol.upper()}  •  {profile.endpoint}  •  {profile.country or 'страна не указана'}")
        self.ping.value.setText(f"{profile.latency_ms} ms" if profile.latency_ms is not None else "-")
        self.protocol.value.setText(profile.protocol.upper())

    def set_health(self, service: str, result: HealthCheckResult) -> None:
        pill = self.health_pills.get(service)
        if not pill:
            return
        text = {
            HealthStatus.UNCHECKED: "Не проверялось",
            HealthStatus.CHECKING: "Проверяется...",
            HealthStatus.OK: "Работает",
            HealthStatus.FAILED: "Не работает",
            HealthStatus.TIMEOUT: "Таймаут",
        }[result.status]
        status = "ok" if result.status == HealthStatus.OK else "warn" if result.status in {HealthStatus.UNCHECKED, HealthStatus.CHECKING} else "error"
        pill.set_status(status, text)

    def render_servers(self, servers: list[Profile]) -> None:
        query = self.search.text().lower().strip() if hasattr(self, "search") else ""
        protocol = self.protocol_filter.currentText().lower() if hasattr(self, "protocol_filter") else "все"
        self.server_tree.setUpdatesEnabled(False)
        try:
            self.server_tree.clear()
            for profile in servers:
                if protocol != "все" and profile.protocol.lower() != protocol:
                    continue
                if query and query not in profile.name.lower() and query not in profile.protocol.lower() and query not in profile.host.lower():
                    continue
                latency = f"{profile.latency_ms} ms" if profile.latency_ms is not None else "-"
                item = QTreeWidgetItem([profile.name, profile.protocol.upper(), latency, profile.status])
                item.setData(0, Qt.ItemDataRole.UserRole, profile.id)
                self.server_tree.addTopLevelItem(item)
        finally:
            self.server_tree.setUpdatesEnabled(True)

    def _emit_selected(self) -> None:
        item = self.server_tree.currentItem()
        if item:
            self.server_selected.emit(str(item.data(0, Qt.ItemDataRole.UserRole)))
