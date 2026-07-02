from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cheburnet.app.app_state import AppState
from cheburnet.app.models.profile import Profile
from cheburnet.app.models.vpn_status import VpnStatus
from cheburnet.app.ui.widgets.glass_card import GlassCard
from cheburnet.app.ui.widgets.status_pill import StatusPill


class ServersPage(QWidget):
    connect_clicked = Signal()
    disconnect_clicked = Signal()
    routing_mode_changed = Signal(str)
    profile_selected = Signal(str)
    import_wireguard_clicked = Signal()
    add_uri_requested = Signal(str)
    delete_clicked = Signal(str)
    check_selected_clicked = Signal(str)
    check_all_clicked = Signal()

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        self.setObjectName("page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(18)

        vpn_card = GlassCard("VPN")
        vpn_top = QHBoxLayout()
        self.vpn_status = QLabel("VPN отключен")
        self.vpn_status.setObjectName("pageTitle")
        self.vpn_pill = StatusPill("Не защищено", "warn")
        vpn_top.addWidget(self.vpn_status)
        vpn_top.addWidget(self.vpn_pill)
        vpn_top.addStretch(1)
        vpn_card.layout.addLayout(vpn_top)
        self.profile = QLabel("Профиль не выбран")
        self.profile.setObjectName("muted")
        vpn_card.layout.addWidget(self.profile)
        self.routing_mode = QComboBox()
        self.routing_mode.addItem("Обычный VPN", "full_vpn")
        self.routing_mode.addItem("Туннелирование", "smart_split")
        self.routing_mode.addItem("Выключен", "zapret_only")
        self.routing_mode.currentIndexChanged.connect(lambda _index: self.routing_mode_changed.emit(str(self.routing_mode.currentData() or "full_vpn")))
        vpn_card.layout.addWidget(self.routing_mode)
        vpn_buttons = QHBoxLayout()
        connect = QPushButton("Подключить")
        connect.setObjectName("primary")
        connect.clicked.connect(lambda _checked=False: self.connect_clicked.emit())
        disconnect = QPushButton("Отключить")
        disconnect.setObjectName("danger")
        disconnect.clicked.connect(lambda _checked=False: self.disconnect_clicked.emit())
        vpn_buttons.addWidget(connect)
        vpn_buttons.addWidget(disconnect)
        vpn_buttons.addStretch(1)
        vpn_card.layout.addLayout(vpn_buttons)
        layout.addWidget(vpn_card)

        card = GlassCard("Серверы")
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по названию, host или протоколу")
        self.protocol = QComboBox()
        self.protocol.addItems(["Все", "VLESS", "VMess", "Trojan", "SS", "Hysteria2", "WireGuard"])
        self.search.textChanged.connect(lambda _text: self.render(self.state.servers))
        self.protocol.currentTextChanged.connect(lambda _text: self.render(self.state.servers))
        filters.addWidget(self.search, 1)
        filters.addWidget(self.protocol)
        card.layout.addLayout(filters)

        buttons = QGridLayout()
        buttons.setHorizontalSpacing(12)
        buttons.setVerticalSpacing(12)
        actions = [
            ("Импорт WireGuard .conf", self.import_wireguard_clicked.emit),
            ("Добавить ссылку профиля", self._ask_uri),
            ("Удалить профиль", self._delete_selected),
            ("Проверить выбранный", self._check_selected),
            ("Проверить все", self.check_all_clicked.emit),
        ]
        for index, (text, callback) in enumerate(actions):
            button = QPushButton(text)
            button.setMinimumWidth(160)
            if text == "Добавить ссылку профиля":
                button.setObjectName("primary")
            button.clicked.connect(lambda _checked=False, current_callback=callback: current_callback())
            buttons.addWidget(button, index // 3, index % 3)
        card.layout.addLayout(buttons)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(7)
        self.tree.setHeaderLabels(["★", "Название", "Протокол", "Host:Port", "Ping", "Статус", "Источник"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setAllColumnsShowFocus(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        for column, width in enumerate((42, 380, 110, 260, 80, 120, 150)):
            self.tree.setColumnWidth(column, width)
        self.tree.itemSelectionChanged.connect(self._emit_selected)
        card.layout.addWidget(self.tree)
        layout.addWidget(card)

        state.servers_changed.connect(self.render)
        state.vpn_status_changed.connect(self.set_status)
        state.selected_profile_changed.connect(self.set_profile)
        self.set_status(state.vpn_status)
        self.set_profile(state.selected_profile)

    def render(self, profiles: list[Profile]) -> None:
        query = self.search.text().lower().strip()
        selected_protocol = self.protocol.currentText().lower()
        self.tree.setUpdatesEnabled(False)
        try:
            self.tree.clear()
            for profile in sorted(profiles, key=lambda p: p.latency_ms if p.latency_ms is not None else 999999):
                if selected_protocol != "все" and profile.protocol.lower() != selected_protocol:
                    continue
                if query and query not in profile.name.lower() and query not in profile.host.lower() and query not in profile.protocol.lower():
                    continue
                item = QTreeWidgetItem(
                    [
                        "★" if profile.favorite else "☆",
                        profile.name,
                        profile.protocol.upper(),
                        profile.endpoint,
                        f"{profile.latency_ms} ms" if profile.latency_ms is not None else "-",
                        profile.status,
                        profile.source,
                    ]
                )
                item.setData(0, Qt.ItemDataRole.UserRole, profile.id)
                self.tree.addTopLevelItem(item)
        finally:
            self.tree.setUpdatesEnabled(True)

    def set_profile(self, profile: Profile | None) -> None:
        self.profile.setText(profile.name if profile else "Профиль не выбран")

    def set_routing_mode(self, mode: str) -> None:
        value = mode if mode in {"full_vpn", "smart_split", "zapret_only"} else "full_vpn"
        index = self.routing_mode.findData(value)
        if index >= 0 and self.routing_mode.currentIndex() != index:
            self.routing_mode.blockSignals(True)
            self.routing_mode.setCurrentIndex(index)
            self.routing_mode.blockSignals(False)

    def set_status(self, status: VpnStatus) -> None:
        if status == VpnStatus.CONNECTED:
            self.vpn_status.setText("VPN подключен")
            self.vpn_pill.set_status("ok", "Защищено")
        elif status == VpnStatus.CONNECTING:
            self.vpn_status.setText("VPN подключается")
            self.vpn_pill.set_status("warn", "Подключение")
        elif status == VpnStatus.DISCONNECTING:
            self.vpn_status.setText("VPN отключается")
            self.vpn_pill.set_status("warn", "Отключение")
        elif status == VpnStatus.ERROR:
            self.vpn_status.setText("Ошибка VPN")
            self.vpn_pill.set_status("error", "Ошибка")
        else:
            self.vpn_status.setText("VPN отключен")
            self.vpn_pill.set_status("warn", "Не защищено")

    def _emit_selected(self) -> None:
        item = self.tree.currentItem()
        if item:
            self.profile_selected.emit(str(item.data(0, Qt.ItemDataRole.UserRole)))

    def _selected_id(self) -> str:
        item = self.tree.currentItem()
        return str(item.data(0, Qt.ItemDataRole.UserRole)) if item else ""

    def _ask_uri(self) -> None:
        value, ok = QInputDialog.getText(self, "Добавить профиль", "VLESS/VMess/Trojan/SS/Hysteria2 URI:")
        if ok and value.strip():
            self.add_uri_requested.emit(value.strip())

    def _delete_selected(self) -> None:
        profile_id = self._selected_id()
        if profile_id:
            self.delete_clicked.emit(profile_id)

    def _check_selected(self) -> None:
        profile_id = self._selected_id()
        if profile_id:
            self.check_selected_clicked.emit(profile_id)
