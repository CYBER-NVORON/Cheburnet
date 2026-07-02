from __future__ import annotations

import json
import sys
from typing import Any, Callable

from PySide6.QtCore import QEvent, QObject, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from cheburnet.app.app_state import AppState
from cheburnet.app.constants import APP_VERSION
from cheburnet.app.controllers.vpn_controller import VpnController
from cheburnet.app.controllers.zapret_controller import ZapretController
from cheburnet.app.core.config import SettingsStore
from cheburnet.app.core.logger import AppLogger
from cheburnet.app.core.paths import app_data_dir, logs_dir
from cheburnet.app.core.system import is_admin, open_path, relaunch_as_admin
from cheburnet.app.core.updater import PreparedUpdate, SelfUpdateService, is_newer_version
from cheburnet.app.models.vpn_status import VpnStatus
from cheburnet.app.models.zapret_status import ZapretStatus
from cheburnet.app.services.free_configs_service import FreeConfigsService
from cheburnet.app.services.healthcheck_service import HealthcheckService
from cheburnet.app.services.profile_store import ProfileStore
from cheburnet.app.services.singbox_config_builder import SingBoxConfigBuilder
from cheburnet.app.services.singbox_service import SingBoxService
from cheburnet.app.services.traffic_monitor import TrafficMonitor
from cheburnet.app.services.wireguard_importer import WireGuardImporter
from cheburnet.app.services.zapret_service import ZapretService
from cheburnet.app.ui.pages.dashboard_page import DashboardPage
from cheburnet.app.ui.pages.logs_page import LogsPage
from cheburnet.app.ui.pages.rules_page import RulesPage
from cheburnet.app.ui.pages.servers_page import ServersPage
from cheburnet.app.ui.pages.settings_page import SettingsPage
from cheburnet.app.ui.pages.updates_page import UpdatesPage
from cheburnet.app.ui.pages.zapret_page import ZapretPage
from cheburnet.app.ui.resources import app_icon
from cheburnet.app.ui.styles import build_qss
from cheburnet.app.ui.widgets.sidebar import Sidebar

TaskFunc = Callable[[Callable[[str], None]], Any]
TRAFFIC_ACTIVE_MS = 1500
TRAFFIC_IDLE_MS = 10000
TRAFFIC_MINIMIZED_MS = 15000


class TaskWorker(QObject):
    progress = Signal(str)
    finished = Signal(str, object)
    failed = Signal(str, str)

    def __init__(self, func: TaskFunc) -> None:
        super().__init__()
        self.func = func
        self.task_id = str(id(self))

    def run(self) -> None:
        try:
            self.finished.emit(self.task_id, self.func(self.progress.emit))
        except Exception as exc:
            self.failed.emit(self.task_id, str(exc))


class AdminDialog(QDialog):
    relaunch_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Нужны права администратора")
        self.setObjectName("page")
        self.setModal(True)
        self.resize(520, 260)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        title = QLabel("Для VPN/TUN и Zapret нужны права администратора")
        title.setObjectName("pageTitle")
        text = QLabel("Без прав администратора можно смотреть настройки, серверы и журнал, но запуск VPN и Zapret будет заблокирован.")
        text.setObjectName("muted")
        text.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(text)
        layout.addStretch(1)
        row = QHBoxLayout()
        relaunch = QPushButton("Перезапустить от администратора")
        relaunch.setObjectName("primary")
        relaunch.clicked.connect(lambda _checked=False: self.relaunch_requested.emit())
        cont = QPushButton("Продолжить без запуска")
        cont.clicked.connect(lambda _checked=False: self.accept())
        row.addWidget(relaunch)
        row.addWidget(cont)
        layout.addLayout(row)


class MainWindow(QMainWindow):
    log_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CheburNet")
        self.resize(1500, 880)
        self.setMinimumSize(860, 560)
        self.setWindowIcon(app_icon())

        self.state = AppState()
        self.state.set_admin(is_admin())
        self.settings = SettingsStore()
        self.profiles = ProfileStore()
        self.log_requested.connect(self.state.add_log)
        self.logger = AppLogger(self.log_requested.emit)
        self.traffic_monitor = TrafficMonitor()
        self.self_update = SelfUpdateService()

        self.singbox = SingBoxService()
        self.zapret_service = ZapretService(self.settings.section("zapret").get("install_dir") or None)
        self.wireguard = WireGuardImporter()
        self.builder = SingBoxConfigBuilder(self.wireguard)
        self.vpn_controller = VpnController(
            self.state,
            self.settings,
            self.profiles,
            self.logger,
            self.singbox,
            self.builder,
            FreeConfigsService(),
            self.wireguard,
            HealthcheckService(),
        )
        self.zapret_controller = ZapretController(self.state, self.settings, self.logger, self.zapret_service, HealthcheckService())
        self.threads: list[QThread] = []
        self.workers: list[tuple[QThread, TaskWorker]] = []
        self.task_callbacks: dict[str, tuple[Callable[[Any], None] | None, Callable[[str], None] | None]] = {}

        self._build_ui()
        self._connect_actions()
        self._init_tray()
        self._bootstrap()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.sidebar = Sidebar()
        layout.addWidget(self.sidebar)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.pages: dict[str, QWidget] = {
            "dashboard": DashboardPage(self.state),
            "vpn": ServersPage(self.state),
            "zapret": ZapretPage(self.state),
            "rules": RulesPage(),
            "logs": LogsPage(self.state),
            "settings": SettingsPage(),
            "updates": UpdatesPage(),
        }
        self.page_containers: dict[str, QScrollArea] = {}
        for key, page in self.pages.items():
            scroll = QScrollArea()
            scroll.setObjectName("pageScroll")
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
            self.page_containers[key] = scroll
        self.setStyleSheet(build_qss(str(self.settings.get("theme", "control_deck"))))
        self._show_page("dashboard")

    def _connect_actions(self) -> None:
        dashboard = self.pages["dashboard"]
        vpn = self.pages["vpn"]
        zapret = self.pages["zapret"]
        rules = self.pages["rules"]
        settings = self.pages["settings"]
        logs = self.pages["logs"]
        updates = self.pages["updates"]

        self.sidebar.page_selected.connect(self._show_page)
        dashboard.power_clicked.connect(self._toggle_vpn)  # type: ignore[attr-defined]
        dashboard.zapret_clicked.connect(self._toggle_zapret_or_download)  # type: ignore[attr-defined]
        dashboard.import_wireguard_clicked.connect(self._import_wireguard)  # type: ignore[attr-defined]
        dashboard.server_selected.connect(self._select_profile)  # type: ignore[attr-defined]
        dashboard.routing_mode_changed.connect(self._save_routing_mode)  # type: ignore[attr-defined]

        vpn.connect_clicked.connect(self._connect_vpn)  # type: ignore[attr-defined]
        vpn.disconnect_clicked.connect(self._disconnect_vpn)  # type: ignore[attr-defined]
        vpn.routing_mode_changed.connect(self._save_routing_mode)  # type: ignore[attr-defined]
        vpn.profile_selected.connect(self._select_profile)  # type: ignore[attr-defined]
        vpn.import_wireguard_clicked.connect(self._import_wireguard)  # type: ignore[attr-defined]
        vpn.add_uri_requested.connect(self._add_uri)  # type: ignore[attr-defined]
        vpn.delete_clicked.connect(self._delete_profile)  # type: ignore[attr-defined]
        vpn.check_selected_clicked.connect(self._check_profile)  # type: ignore[attr-defined]
        vpn.check_all_clicked.connect(self._check_all_profiles)  # type: ignore[attr-defined]

        zapret.download_clicked.connect(self._download_zapret)  # type: ignore[attr-defined]
        zapret.start_clicked.connect(self._start_zapret)  # type: ignore[attr-defined]
        zapret.stop_clicked.connect(self._stop_zapret)  # type: ignore[attr-defined]
        zapret.choose_folder_clicked.connect(self._choose_zapret_folder)  # type: ignore[attr-defined]
        zapret.update_ipset_clicked.connect(self._update_zapret_ipset)  # type: ignore[attr-defined]
        zapret.update_hosts_clicked.connect(self._update_zapret_hosts)  # type: ignore[attr-defined]
        zapret.diagnostics_clicked.connect(self._run_zapret_diagnostics)  # type: ignore[attr-defined]
        zapret.check_services_clicked.connect(self._check_zapret_services)  # type: ignore[attr-defined]
        zapret.test_all_clicked.connect(self._test_zapret_scripts)  # type: ignore[attr-defined]
        zapret.stop_test_clicked.connect(self._stop_zapret_test)  # type: ignore[attr-defined]
        zapret.mode_changed.connect(self._save_zapret_mode)  # type: ignore[attr-defined]
        zapret.script_changed.connect(self._save_zapret_script)  # type: ignore[attr-defined]
        zapret.options_changed.connect(self._save_zapret_options)  # type: ignore[attr-defined]

        rules.save_clicked.connect(self._save_rules)  # type: ignore[attr-defined]
        settings.save_clicked.connect(self._save_settings)  # type: ignore[attr-defined]
        settings.open_data_clicked.connect(lambda: open_path(app_data_dir()))  # type: ignore[attr-defined]
        settings.open_log_clicked.connect(lambda: open_path(logs_dir()))  # type: ignore[attr-defined]
        settings.reset_clicked.connect(self._reset_settings)  # type: ignore[attr-defined]
        logs.clear_clicked.connect(self._clear_logs)  # type: ignore[attr-defined]
        updates.check_clicked.connect(self._check_updates)  # type: ignore[attr-defined]
        updates.update_app_clicked.connect(self._update_app)  # type: ignore[attr-defined]
        updates.update_singbox_clicked.connect(self._update_singbox)  # type: ignore[attr-defined]
        updates.update_zapret_clicked.connect(self._download_zapret)  # type: ignore[attr-defined]

        self.state.traffic_changed.connect(lambda data: self.sidebar.set_traffic(float(data.get("download_mbps", 0)), float(data.get("upload_mbps", 0))))
        self.state.vpn_status_changed.connect(lambda _status: self._update_traffic_timer())

    def _bootstrap(self) -> None:
        self.sidebar.set_admin(self.state.is_admin)
        self.logger.info("Приложение запущено")
        self.logger.info(f"Проверка прав администратора: {'OK' if self.state.is_admin else 'нет прав'}")
        try:
            self.self_update.cleanup_old_updates()
            self.singbox.cleanup_old_downloads()
        except Exception as exc:
            self.logger.warning(f"Очистка временных файлов обновлений: {exc}")
        self.vpn_controller.load_profiles()
        self._refresh_scripts(check_process=False)
        self._refresh_settings_pages()
        self.traffic_timer = QTimer(self)
        self.traffic_timer.timeout.connect(self._sample_traffic)
        self.traffic_timer.start(self._traffic_interval())
        self._sample_traffic()
        if not self.state.is_admin:
            QTimer.singleShot(250, self._show_admin_dialog)
        else:
            QTimer.singleShot(700, self._autostart_services)

    def _show_page(self, key: str) -> None:
        page = self.pages.get(key)
        if not page:
            return
        self.stack.setCurrentWidget(self.page_containers.get(key, page))
        self.sidebar.set_active(key)
        if key == "zapret":
            self._refresh_scripts(check_process=True)

    def _show_admin_dialog(self) -> None:
        dialog = AdminDialog(self)
        dialog.setStyleSheet(build_qss(str(self.settings.get("theme", "control_deck"))))
        dialog.relaunch_requested.connect(self._relaunch_admin)
        dialog.exec()

    def _relaunch_admin(self) -> None:
        try:
            relaunch_as_admin()
            QApplication.quit()
        except Exception as exc:
            QMessageBox.warning(self, "Администратор", str(exc))

    def _require_admin(self) -> bool:
        if self.state.is_admin:
            return True
        self._show_admin_dialog()
        return False

    def _run_task(
        self,
        func: TaskFunc,
        done: Callable[[Any], None] | None = None,
        failed: Callable[[str], None] | None = None,
    ) -> None:
        thread = QThread(self)
        worker = TaskWorker(func)
        worker.moveToThread(thread)
        self.workers.append((thread, worker))
        self.task_callbacks[worker.task_id] = (done, failed)
        thread.started.connect(worker.run)
        worker.progress.connect(self._task_progress)
        worker.finished.connect(self._task_finished)
        worker.failed.connect(self._task_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._cleanup_thread(thread))
        self.threads.append(thread)
        thread.start()

    def _cleanup_thread(self, thread: QThread) -> None:
        if thread in self.threads:
            self.threads.remove(thread)
        for task_thread, worker in list(self.workers):
            if task_thread is thread:
                self.task_callbacks.pop(worker.task_id, None)
        self.workers = [(task_thread, worker) for task_thread, worker in self.workers if task_thread is not thread]
        thread.deleteLater()

    @Slot(str)
    def _task_progress(self, message: str) -> None:
        if message.startswith("zapret_test_row:"):
            try:
                row = json.loads(message.removeprefix("zapret_test_row:"))
            except json.JSONDecodeError:
                self.logger.warning("Zapret test row parse failed")
                return
            self.pages["zapret"].append_test_result(row)  # type: ignore[attr-defined]
            return
        self.logger.info(message)

    @Slot(str, object)
    def _task_finished(self, task_id: str, result: object) -> None:
        done, _failed = self.task_callbacks.get(task_id, (None, None))
        if done:
            done(result)

    @Slot(str, str)
    def _task_failed(self, task_id: str, message: str) -> None:
        _done, failed = self.task_callbacks.get(task_id, (None, None))
        if failed:
            failed(message)
        else:
            self._show_error(message)

    def _show_error(self, message: str) -> None:
        self.logger.error(message)
        if message.startswith("VPN health-check не прошёл"):
            return
        QMessageBox.warning(self, "CheburNet", f"{message}\n\nЖурнал: {logs_dir() / 'cheburnet.log'}")

    def _toggle_vpn(self) -> None:
        if self.state.vpn_status in {VpnStatus.CONNECTED, VpnStatus.CONNECTING, VpnStatus.DISCONNECTING}:
            self._disconnect_vpn()
        else:
            self._connect_vpn()

    def _connect_vpn(self) -> None:
        if not self._require_admin():
            return
        if str(self.settings.get("routing_mode", "full_vpn")) == "zapret_only":
            if self.state.vpn_status in {VpnStatus.CONNECTED, VpnStatus.CONNECTING}:
                self._disconnect_vpn()
            self.logger.info("VPN выключен выбранным режимом")
            return
        self._run_task(lambda progress: self.vpn_controller.connect_selected_profile(progress))

    def _disconnect_vpn(self) -> None:
        self._run_task(lambda _progress: self.vpn_controller.disconnect())

    def _autostart_services(self) -> None:
        vpn_auto = bool(self.settings.section("vpn").get("auto_connect", False))
        zapret_auto = bool(self.settings.section("zapret").get("autostart_with_app", False))
        if zapret_auto and self.state.zapret_status != ZapretStatus.RUNNING:
            if not self.zapret_service.is_installed():
                self.logger.warning("Запуск Zapret вместе с CheburNet пропущен: Zapret не установлен")
                self._autostart_vpn(vpn_auto)
                return
            self.logger.info("Запуск Zapret вместе с CheburNet")
            self._run_task(
                lambda _progress: self.zapret_controller.start(),
                done=lambda _result: self._autostart_vpn(vpn_auto),
                failed=lambda message: (self.logger.error(f"Запуск Zapret вместе с CheburNet: {message}"), self._autostart_vpn(vpn_auto)),
            )
            return
        self._autostart_vpn(vpn_auto)

    def _autostart_vpn(self, enabled: bool) -> None:
        if not enabled:
            return
        if str(self.settings.get("routing_mode", "full_vpn")) == "zapret_only":
            self.logger.info("Автоподключение VPN пропущено: режим VPN выключен")
            return
        if self.state.vpn_status in {VpnStatus.CONNECTED, VpnStatus.CONNECTING}:
            return
        self.logger.info("Автоподключение VPN")
        self._run_task(lambda progress: self.vpn_controller.connect_selected_profile(progress), failed=lambda message: self.logger.error(f"Автоподключение VPN: {message}"))

    def _toggle_zapret_or_download(self) -> None:
        if self.state.zapret_status == ZapretStatus.NOT_INSTALLED:
            self._download_zapret()
        elif self.state.zapret_status == ZapretStatus.RUNNING:
            self._stop_zapret()
        else:
            self._start_zapret()

    def _download_zapret(self) -> None:
        self._run_task(lambda progress: self.zapret_controller.download_or_update(progress), done=lambda _root: (self._refresh_scripts(), self._refresh_settings_pages()))

    def _choose_zapret_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Папка Flowseal zapret-discord-youtube")
        if not path:
            return
        try:
            self.zapret_controller.set_install_dir(path)
            self._refresh_scripts()
            self._refresh_settings_pages()
        except Exception as exc:
            self._show_error(str(exc))

    def _show_zapret_info(self, message: object) -> None:
        QMessageBox.information(self, "Zapret", str(message))

    def _update_zapret_ipset(self) -> None:
        self._run_task(
            lambda _progress: self.zapret_controller.update_ipset_list(),
            done=lambda message: (self._show_zapret_info(message), self.pages["zapret"].set_options(self.zapret_controller.options())),  # type: ignore[attr-defined]
        )

    def _update_zapret_hosts(self) -> None:
        if not self._require_admin():
            return
        self._run_task(lambda _progress: self.zapret_controller.update_hosts_file(), done=self._show_zapret_info)

    def _run_zapret_diagnostics(self) -> None:
        self._run_task(lambda _progress: self.zapret_controller.run_diagnostics(), done=self._show_zapret_info)

    def _start_zapret(self) -> None:
        if not self._require_admin():
            return
        page = self.pages["zapret"]
        script = None if page.mode() == "auto" else page.selected_script()  # type: ignore[attr-defined]
        was_vpn_connected = self.state.vpn_status == VpnStatus.CONNECTED

        def refresh_vpn_routes(_result: Any) -> None:
            if not was_vpn_connected or self.state.zapret_status != ZapretStatus.RUNNING:
                return
            self.logger.info("Zapret включен: пересобираю VPN-маршруты для YouTube/Discord")
            self._run_task(lambda progress: self.vpn_controller.connect_selected_profile(progress))

        self._run_task(lambda _progress: self.zapret_controller.start(script), done=refresh_vpn_routes)

    def _stop_zapret(self) -> None:
        was_vpn_connected = self.state.vpn_status == VpnStatus.CONNECTED

        def refresh_vpn_routes(_result: Any) -> None:
            if not was_vpn_connected or self.state.vpn_status != VpnStatus.CONNECTED:
                return
            self.logger.info("Zapret выключен: пересобираю VPN-маршруты")
            self._run_task(lambda progress: self.vpn_controller.connect_selected_profile(progress))

        self._run_task(lambda _progress: self.zapret_controller.stop(), done=refresh_vpn_routes)

    def _import_wireguard(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "WireGuard .conf", "", "WireGuard config (*.conf);;All files (*)")
        if not path:
            return
        try:
            self.vpn_controller.import_wireguard(path)
        except Exception as exc:
            self._show_error(str(exc))

    def _add_uri(self, uri: str) -> None:
        try:
            self.vpn_controller.add_uri(uri)
        except Exception as exc:
            self._show_error(str(exc))

    def _select_profile(self, profile_id: str) -> None:
        self.vpn_controller.select_profile(profile_id)

    def _delete_profile(self, profile_id: str) -> None:
        self.vpn_controller.delete_profile(profile_id)

    def _check_profile(self, profile_id: str) -> None:
        profile = self.profiles.get(profile_id)
        if profile:
            self._run_task(lambda _progress: self.vpn_controller.check_profile(profile, force=True))

    def _check_all_profiles(self) -> None:
        profiles = self.profiles.all()
        self._run_task(lambda progress: self.vpn_controller.check_profiles(profiles, progress=progress))

    def _save_rules(self, domains: list[str]) -> None:
        self.settings.update({"routing": {"direct_domains": domains}})
        self.logger.info("Правила маршрутизации сохранены")
        self._refresh_settings_pages()

    def _save_settings(self, values: dict[str, Any]) -> None:
        previous_mode = str(self.settings.get("routing_mode", "full_vpn"))
        self.settings.update(values)
        self.logger.info("Настройки сохранены")
        self.setStyleSheet(build_qss(str(self.settings.get("theme", "control_deck"))))
        self._refresh_settings_pages()
        current_mode = str(self.settings.get("routing_mode", "full_vpn"))
        if current_mode == "zapret_only" and self.state.vpn_status in {VpnStatus.CONNECTED, VpnStatus.CONNECTING}:
            self._disconnect_vpn()
            return
        if previous_mode != current_mode and self.state.vpn_status == VpnStatus.CONNECTED:
            self._run_task(lambda progress: self.vpn_controller.connect_selected_profile(progress))

    def _save_routing_mode(self, mode: str) -> None:
        previous_mode = str(self.settings.get("routing_mode", "full_vpn"))
        self.settings.set("routing_mode", mode)
        self._refresh_settings_pages()
        if previous_mode != mode:
            self.logger.info(f"Режим VPN: {mode}")
        if mode == "zapret_only" and self.state.vpn_status in {VpnStatus.CONNECTED, VpnStatus.CONNECTING}:
            self._disconnect_vpn()
            return
        if previous_mode != mode and self.state.vpn_status == VpnStatus.CONNECTED:
            self._run_task(lambda progress: self.vpn_controller.connect_selected_profile(progress))

    def _save_zapret_mode(self, mode: str) -> None:
        self.settings.update({"zapret": {"mode": mode}})
        self.logger.info(f"Zapret режим: {mode}")

    def _save_zapret_script(self, script: str) -> None:
        self.zapret_controller.set_selected_script(script)
        self._refresh_settings_pages()

    def _save_zapret_options(self, values: dict[str, object]) -> None:
        try:
            self.zapret_controller.save_options(values)
            self.pages["zapret"].set_options(self.zapret_controller.options())  # type: ignore[attr-defined]
        except Exception as exc:
            self._show_error(str(exc))

    def _reset_settings(self) -> None:
        self.settings.path.unlink(missing_ok=True)
        self.settings.load()
        self._refresh_settings_pages()
        self.logger.warning("Настройки сброшены")

    def _clear_logs(self) -> None:
        self.state.clear_logs()
        self.pages["logs"].console.clear()  # type: ignore[attr-defined]

    def _check_updates(self) -> None:
        updates = self.pages["updates"]
        updates.set_checking()  # type: ignore[attr-defined]

        def work(_progress: Callable[[str], None]) -> dict[str, dict[str, str]]:
            def short_error(exc: Exception) -> str:
                text = str(exc)
                if "10054" in text:
                    return "Соединение сброшено"
                if "timed out" in text.lower() or "timeout" in text.lower():
                    return "Таймаут"
                if "urlopen error" in text:
                    return "Сеть недоступна"
                return text[:80]

            data: dict[str, dict[str, str]] = {
                "app": {"status": "neutral", "version": APP_VERSION, "note": "Запрос"},
                "singbox": {"status": "neutral", "version": "—", "note": "Не проверялось"},
                "zapret": {"status": "neutral", "version": "—", "note": "Не проверялось"},
            }
            try:
                app_info = self.self_update.version_info()
                data["app"] = {"status": app_info.status, "version": app_info.current, "note": app_info.detail}
            except Exception as exc:
                data["app"] = {"status": "error", "version": APP_VERSION, "note": short_error(exc)}

            current_singbox = self.singbox.version() or "не установлен"
            try:
                latest = self.singbox.latest_release()
                latest_singbox = str(latest.get("tag_name") or latest.get("name") or "latest")
                status = "warn" if current_singbox == "не установлен" or is_newer_version(latest_singbox, current_singbox) else "ok"
                data["singbox"] = {
                    "status": status,
                    "version": current_singbox,
                    "note": "Актуально" if status == "ok" else f"Доступно {latest_singbox}",
                }
            except Exception as exc:
                data["singbox"] = {"status": "error", "version": current_singbox, "note": short_error(exc)}

            local_zapret = self.zapret_service.local_version() or ("установлен" if self.zapret_service.is_installed() else "не установлен")
            try:
                latest_z = self.zapret_service.latest_release()
                latest_zapret = str(latest_z.get("tag_name") or latest_z.get("name") or "latest")
                status = "ok" if latest_zapret == local_zapret else "warn"
                if local_zapret == "не установлен":
                    status = "warn"
                data["zapret"] = {
                    "status": status,
                    "version": local_zapret,
                    "note": "Актуально" if status == "ok" else f"Доступно {latest_zapret}",
                }
            except Exception as exc:
                data["zapret"] = {"status": "error", "version": local_zapret, "note": short_error(exc)}
            return data

        self._run_task(work, done=lambda data: updates.set_versions(dict(data)))  # type: ignore[attr-defined]

    def _update_app(self) -> None:
        self._run_task(
            lambda progress: self.self_update.prepare_update(progress),
            done=self._apply_app_update,
        )

    def _apply_app_update(self, prepared: PreparedUpdate) -> None:
        answer = QMessageBox.question(
            self,
            "Обновление CheburNet",
            "Обновление готово. CheburNet закроется, заменит файлы и запустится снова.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.logger.info("Обновление CheburNet подготовлено, установка отложена")
            return
        try:
            self.singbox.stop()
        except Exception:
            pass
        try:
            self.zapret_service.stop()
        except Exception:
            pass
        self.logger.flush()
        self.self_update.start_update_and_exit(prepared)
        QApplication.quit()

    def _update_singbox(self) -> None:
        self._run_task(lambda progress: self.singbox.download_latest(progress), done=lambda path: self.logger.info(f"sing-box обновлен: {path}"))

    def _refresh_scripts(self, check_process: bool = False) -> None:
        scripts = self.zapret_controller.scripts()
        selected = str(self.settings.section("zapret").get("selected_script") or "")
        self.pages["zapret"].set_scripts(scripts, selected)  # type: ignore[attr-defined]
        self.zapret_controller.refresh_status(check_process=check_process)
        self.pages["zapret"].set_mode(str(self.settings.section("zapret").get("mode", "auto")))  # type: ignore[attr-defined]
        self.pages["zapret"].set_options(self.zapret_controller.options())  # type: ignore[attr-defined]

    def _check_zapret_services(self) -> None:
        self._run_task(lambda _progress: self.zapret_controller.check_services())

    def _test_zapret_scripts(self) -> None:
        self.pages["zapret"].set_test_results([])  # type: ignore[attr-defined]
        self.pages["zapret"].set_test_running(True)  # type: ignore[attr-defined]
        self._run_task(
            lambda progress: self.zapret_controller.test_all_scripts(progress),
            done=self._finish_zapret_test,
            failed=lambda message: (self.pages["zapret"].set_test_running(False), self._show_error(message)),  # type: ignore[attr-defined]
        )

    def _finish_zapret_test(self, rows: object) -> None:
        page = self.pages["zapret"]
        page.set_test_running(False)  # type: ignore[attr-defined]
        if page.results_table.rowCount() == 0:  # type: ignore[attr-defined]
            page.set_test_results(list(rows) if isinstance(rows, list) else [])  # type: ignore[attr-defined]
        self._refresh_scripts()

    def _stop_zapret_test(self) -> None:
        self.zapret_controller.cancel_test()

    def _refresh_settings_pages(self) -> None:
        self.pages["settings"].set_values(self.settings.data)  # type: ignore[attr-defined]
        routing = self.settings.section("routing")
        self.pages["rules"].set_domains(list(routing.get("direct_domains", [])))  # type: ignore[attr-defined]
        self.pages["zapret"].set_mode(str(self.settings.section("zapret").get("mode", "auto")))  # type: ignore[attr-defined]
        self.pages["dashboard"].set_routing_mode(str(self.settings.get("routing_mode", "full_vpn")))  # type: ignore[attr-defined]
        self.pages["vpn"].set_routing_mode(str(self.settings.get("routing_mode", "full_vpn")))  # type: ignore[attr-defined]

    def _sample_traffic(self) -> None:
        traffic = self.traffic_monitor.sample(self.state.vpn_status == VpnStatus.CONNECTED)
        self.state.set_traffic(traffic)
        self._update_traffic_timer()

    def _traffic_interval(self) -> int:
        if self.isMinimized():
            return TRAFFIC_MINIMIZED_MS
        if self.state.vpn_status == VpnStatus.CONNECTED:
            return TRAFFIC_ACTIVE_MS
        return TRAFFIC_IDLE_MS

    def _update_traffic_timer(self) -> None:
        if not hasattr(self, "traffic_timer"):
            return
        interval = self._traffic_interval()
        if self.traffic_timer.interval() != interval:
            self.traffic_timer.setInterval(interval)

    def _init_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        menu = QMenu()
        open_action = QAction("Открыть CheburNet", self)
        open_action.triggered.connect(self.showNormal)
        vpn_action = QAction("Подключить/отключить VPN", self)
        vpn_action.triggered.connect(self._toggle_vpn)
        zapret_action = QAction("Включить/выключить Zapret", self)
        zapret_action.triggered.connect(self._toggle_zapret_or_download)
        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(QApplication.quit)
        for action in (open_action, vpn_action, zapret_action, quit_action):
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            self.singbox.stop()
        except Exception as exc:
            self.logger.error(f"Ошибка остановки sing-box: {exc}")
        try:
            self.zapret_service.stop()
        except Exception as exc:
            self.logger.error(f"Ошибка остановки Zapret: {exc}")
        self.logger.flush()
        event.accept()

    def changeEvent(self, event) -> None:  # type: ignore[override]
        if event.type() == QEvent.Type.WindowStateChange:
            self._update_traffic_timer()
        super().changeEvent(event)


def run_app() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("CheburNet")
    window = MainWindow()
    window.show()
    return app.exec()
