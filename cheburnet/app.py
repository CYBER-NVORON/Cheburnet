from __future__ import annotations

import math
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from cheburnet.config import SettingsStore
from cheburnet.controllers.routes import RouteManager
from cheburnet.controllers.singbox import SingBoxController
from cheburnet.controllers.system import enable_dpi_awareness, is_admin, open_folder
from cheburnet.controllers.vpn import VpnController
from cheburnet.controllers.zapret import ZapretController


THEMES = {
    "dark": {
        "bg": "#111318",
        "surface": "#191d25",
        "surface2": "#222834",
        "text": "#f2f5f7",
        "muted": "#9aa7b5",
        "accent": "#34d399",
        "accent2": "#38bdf8",
        "danger": "#fb7185",
        "warning": "#facc15",
        "line": "#2b3340",
        "entry": "#0f1218",
    },
    "light": {
        "bg": "#eef2f5",
        "surface": "#ffffff",
        "surface2": "#e6edf3",
        "text": "#101820",
        "muted": "#51606f",
        "accent": "#0f9f6e",
        "accent2": "#1677c9",
        "danger": "#d83b55",
        "warning": "#b7791f",
        "line": "#cfd8e3",
        "entry": "#ffffff",
    },
}


class CheburnetApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.store = SettingsStore()
        self.zapret = ZapretController()
        self.vpn = VpnController()
        self.routes = RouteManager()
        self.singbox = SingBoxController()
        self.theme_name = str(self.store.get("theme", "dark"))
        self.colors = THEMES.get(self.theme_name, THEMES["dark"])
        self.current_tab = "dashboard"
        self.widgets_by_tab: dict[str, tk.Frame] = {}
        self.nav_buttons: dict[str, tk.Button] = {}
        self.gradient_phase = 0.0
        self.header_generation = 0
        self.zapret_test_stop = threading.Event()
        self.is_closing = False
        self.title("Cheburnet")
        self._apply_window_icon()
        self.geometry(str(self.store.get("window_geometry", "1180x760")))
        self.minsize(1040, 680)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._configure_style()
        self._build_layout()
        self.after(1200, self._maybe_autostart)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Cheb.TCombobox",
            fieldbackground=self.colors["entry"],
            background=self.colors["surface2"],
            foreground=self.colors["text"],
            bordercolor=self.colors["line"],
            arrowcolor=self.colors["text"],
        )

    def _apply_window_icon(self) -> None:
        ico = self._resource_path("assets/cheburnet.ico")
        png = self._resource_path("assets/cheburnet.png")
        if ico.exists():
            try:
                self.iconbitmap(str(ico))
            except tk.TclError:
                pass
        if png.exists():
            try:
                self.iconphoto(True, tk.PhotoImage(file=str(png)))
            except tk.TclError:
                pass

    @staticmethod
    def _resource_path(relative: str) -> Path:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        return base / relative

    def _build_layout(self) -> None:
        self.configure(bg=self.colors["bg"])
        self.root_frame = tk.Frame(self, bg=self.colors["bg"])
        self.root_frame.pack(fill="both", expand=True)

        self.sidebar_width = self._sidebar_width()
        self.sidebar = tk.Frame(self.root_frame, bg=self.colors["surface"], width=self.sidebar_width)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.main = tk.Frame(self.root_frame, bg=self.colors["bg"])
        self.main.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._build_header()
        self.content = tk.Frame(self.main, bg=self.colors["bg"])
        self.content.pack(fill="both", expand=True, padx=18, pady=(14, 18))

        self.widgets_by_tab = {
            "dashboard": self._dashboard_tab(),
            "zapret": self._zapret_tab(),
            "vpn": self._vpn_tab(),
            "rules": self._rules_tab(),
            "whitelist": self._whitelist_tab(),
            "settings": self._settings_tab(),
        }
        self._show_tab(self.current_tab)

    def _build_sidebar(self) -> None:
        title = tk.Label(
            self.sidebar,
            text="Cheburnet",
            bg=self.colors["surface"],
            fg=self.colors["text"],
            font=("Segoe UI Semibold", 22),
        )
        title.pack(anchor="w", padx=22, pady=(24, 4))
        subtitle = tk.Label(
            self.sidebar,
            text="zapret + VPN router",
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        )
        subtitle.pack(anchor="w", padx=22, pady=(0, 22))
        tabs = [
            ("dashboard", "Пульт"),
            ("zapret", "YouTube / Discord"),
            ("vpn", "VPN"),
            ("rules", "Туннель сайтов"),
            ("whitelist", "Белые списки"),
            ("settings", "Настройки"),
        ]
        self.nav_buttons.clear()
        for key, label in tabs:
            button = self._button(self.sidebar, label, lambda k=key: self._show_tab(k), flat=True)
            button.pack(fill="x", padx=14, pady=5)
            self.nav_buttons[key] = button

        admin_text = "Admin: да" if is_admin() else "Admin: нет"
        color = self.colors["accent"] if is_admin() else self.colors["warning"]
        tk.Label(
            self.sidebar,
            text=admin_text,
            bg=self.colors["surface"],
            fg=color,
            font=("Segoe UI Semibold", 10),
        ).pack(side="bottom", anchor="w", padx=22, pady=(0, 22))

    def _sidebar_width(self) -> int:
        labels = ["Cheburnet", "YouTube / Discord", "Туннель сайтов", "Белые списки", "Настройки"]
        font = ("Segoe UI Semibold", 10)
        measure = tk.Label(self, font=font)
        try:
            widths = []
            for label in labels:
                measure.configure(text=label)
                measure.update_idletasks()
                widths.append(measure.winfo_reqwidth())
        finally:
            measure.destroy()
        return max(350, min(360, max(widths, default=180) + 64))

    def _build_header(self) -> None:
        self.header_generation += 1
        self.header = tk.Canvas(self.main, height=116, bg=self.colors["bg"], highlightthickness=0)
        self.header.pack(fill="x")
        self._draw_header_gradient(self.header_generation)

    def _draw_header_gradient(self, generation: int) -> None:
        if generation != self.header_generation:
            return
        if not hasattr(self, "header") or not self.header.winfo_exists():
            return
        self.header.delete("all")
        width = max(self.header.winfo_width(), 1)
        height = 116
        steps = max(240, min(520, width // 2))
        for index in range(steps):
            pos = index / max(steps - 1, 1)
            wave_a = 0.5 + 0.5 * math.sin((pos * 1.35 + self.gradient_phase) * math.tau)
            wave_b = 0.5 + 0.5 * math.sin((pos * 2.10 - self.gradient_phase * 0.7 + 0.22) * math.tau)
            base = self._blend(self.colors["accent2"], self.colors["accent"], 0.22 + wave_a * 0.45)
            color = self._blend(base, self.colors["surface2"], 0.18 + wave_b * 0.20)
            x0 = int(width * index / steps)
            x1 = int(width * (index + 1) / steps) + 1
            self.header.create_rectangle(x0, 0, x1, height, fill=color, outline=color)
        self.header.create_text(
            28,
            32,
            anchor="w",
            text="Пульт сети",
            fill="#ffffff",
            font=("Segoe UI Semibold", 24),
        )
        self.header.create_text(
            28,
            90,
            anchor="w",
            text="Zapret для YouTube/Discord, sing-box для правил по сайтам, VPN для остального трафика.",
            fill="#eef7ff",
            font=("Segoe UI", 11),
        )
        self.gradient_phase = (self.gradient_phase + 0.009) % 1.0
        self.after(33, lambda: self._draw_header_gradient(generation))

    def _dashboard_tab(self) -> tk.Frame:
        frame = self._tab_frame()
        grid = tk.Frame(frame, bg=self.colors["bg"])
        grid.pack(fill="both", expand=True)

        status_card = self._card(grid)
        status_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 10))
        actions_card = self._card(grid)
        actions_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 10))
        bottom = self._card(grid)
        bottom.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        grid.columnconfigure(0, weight=3, uniform="dashboard")
        grid.columnconfigure(1, weight=2, uniform="dashboard")
        grid.rowconfigure(0, weight=0)
        grid.rowconfigure(1, weight=1)

        self._section_title(status_card, "Состояние")
        self.dashboard_status = tk.Label(
            status_card,
            text=self._status_text(),
            bg=self.colors["surface"],
            fg=self.colors["text"],
            justify="left",
            font=("Segoe UI", 11),
            wraplength=560,
        )
        self.dashboard_status.pack(anchor="w", padx=18, pady=(8, 18))

        status_note = tk.Label(
            status_card,
            text=self._dashboard_note_text(),
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            justify="left",
            font=("Segoe UI", 10),
            wraplength=560,
        )
        status_note.pack(anchor="w", fill="x", padx=18, pady=(0, 18))

        self._section_title(actions_card, "Быстрые действия")
        actions = tk.Frame(actions_card, bg=self.colors["surface"])
        actions.pack(fill="x", padx=18, pady=(8, 18))
        for label, command, danger in [
            ("Запустить лучший zapret", self._start_best_zapret, False),
            ("Остановить zapret", self._stop_zapret, True),
            ("YouTube / Discord", lambda: self._show_tab("zapret"), False),
            ("VPN профили", lambda: self._show_tab("vpn"), False),
            ("Туннель сайтов", lambda: self._show_tab("rules"), False),
            ("Белые списки", lambda: self._show_tab("whitelist"), False),
        ]:
            self._button(actions, label, command, danger=danger).pack(fill="x", pady=4)

        self._section_title(bottom, "Журнал")
        self.log = self._text(bottom, height=10)
        self.log.pack(fill="both", expand=True, padx=18, pady=(8, 18))
        self._log("Приложение запущено. Системные настройки сохраняются автоматически.")
        return frame

    def _zapret_tab(self) -> tk.Frame:
        frame = self._tab_frame()
        top = self._card(frame)
        top.pack(fill="x", pady=(0, 14))
        self._section_title(top, "Zapret для YouTube и Discord")
        row = tk.Frame(top, bg=self.colors["surface"])
        row.pack(fill="x", padx=18, pady=(4, 12))
        self.zapret_dir_var = tk.StringVar(value=str(self.store.get("zapret_dir", "")))
        entry = self._entry(row, self.zapret_dir_var)
        entry.pack(side="left", fill="x", expand=True)
        self._button(row, "Папка", self._browse_zapret_dir).pack(side="left", padx=(8, 0))
        self._button(row, "Скачать latest", self._download_zapret).pack(side="left", padx=(8, 0))

        middle = tk.Frame(frame, bg=self.colors["bg"])
        middle.pack(fill="both", expand=True)
        configs_card = self._card(middle)
        configs_card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        log_card = self._card(middle)
        log_card.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self._section_title(configs_card, "Стратегии")
        self.config_list = tk.Listbox(
            configs_card,
            bg=self.colors["entry"],
            fg=self.colors["text"],
            selectbackground=self.colors["accent2"],
            selectforeground="#ffffff",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.colors["line"],
            activestyle="none",
            font=("Segoe UI", 10),
        )
        self.config_list.pack(fill="both", expand=True, padx=18, pady=(8, 12))
        row2 = tk.Frame(configs_card, bg=self.colors["surface"])
        row2.pack(fill="x", padx=18, pady=(0, 18))
        self._button(row2, "Обновить", self._refresh_configs).pack(side="left", padx=(0, 8))
        self._button(row2, "Тест всех", self._test_zapret_configs).pack(side="left", padx=8)
        self._button(row2, "Запуск", self._start_selected_zapret).pack(side="left", padx=8)
        self._button(row2, "Стоп", self._stop_zapret, danger=True).pack(side="left", padx=8)

        self._section_title(log_card, "Проверка")
        self.zapret_log = self._text(log_card, height=20)
        self.zapret_log.pack(fill="both", expand=True, padx=18, pady=(8, 18))
        self._refresh_configs()
        return frame

    def _vpn_tab(self) -> tk.Frame:
        frame = self._tab_frame()
        left = self._card(frame)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right = self._card(frame)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self._section_title(left, "VPN профили")
        self.profile_list = tk.Listbox(
            left,
            bg=self.colors["entry"],
            fg=self.colors["text"],
            selectbackground=self.colors["accent2"],
            selectforeground="#ffffff",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.colors["line"],
            activestyle="none",
            font=("Segoe UI", 10),
        )
        self.profile_list.pack(fill="both", expand=True, padx=18, pady=(8, 12))
        row = tk.Frame(left, bg=self.colors["surface"])
        row.pack(fill="x", padx=18, pady=(0, 18))
        self._button(row, "WireGuard .conf", self._import_wireguard).pack(side="left", padx=(0, 8))
        self._button(row, "OpenVPN .ovpn", self._import_openvpn).pack(side="left", padx=8)
        self._button(row, "WARP CLI", self._add_warp_profile).pack(side="left", padx=8)
        installers = tk.Frame(left, bg=self.colors["surface"])
        installers.pack(fill="x", padx=18, pady=(0, 18))
        self._button(installers, "Установить WireGuard", lambda: self._install_vpn_component("wireguard")).pack(
            side="left", padx=(0, 8)
        )
        self._button(installers, "Установить OpenVPN", lambda: self._install_vpn_component("openvpn")).pack(
            side="left", padx=8
        )
        self._button(installers, "Установить WARP", lambda: self._install_vpn_component("warp")).pack(side="left", padx=8)
        tk.Label(
            left,
            text="Для режима `Туннель сайтов` системный WireGuard включать не нужно: sing-box поднимает WireGuard сам из .conf.",
            bg=self.colors["surface"],
            fg=self.colors["warning"],
            wraplength=430,
            justify="left",
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=18, pady=(0, 12))
        row2 = tk.Frame(left, bg=self.colors["surface"])
        row2.pack(fill="x", padx=18, pady=(0, 18))
        self._button(row2, "Подключить системный VPN", self._connect_vpn).pack(side="left", padx=(0, 8))
        self._button(row2, "Отключить", self._disconnect_vpn, danger=True).pack(side="left", padx=8)
        self._button(row2, "Удалить", self._remove_vpn_profile, danger=True).pack(side="left", padx=8)

        self._section_title(right, "Инструменты")
        self.vpn_status = self._text(right, height=22)
        self.vpn_status.pack(fill="both", expand=True, padx=18, pady=(8, 12))
        self._button(right, "Проверить WireGuard/OpenVPN/WARP", self._refresh_vpn_status).pack(
            anchor="w", padx=18, pady=(0, 18)
        )
        self._render_profiles()
        self._refresh_vpn_status()
        return frame

    def _rules_tab(self) -> tk.Frame:
        frame = self._tab_frame()
        top = self._card(frame)
        top.pack(fill="x", pady=(0, 14))
        self._section_title(top, "Туннель по сайтам")
        profile = self._selected_profile_from_store()
        protocol = str(profile.get("protocol", "нет профиля")) if profile else "нет профиля"
        name = str(profile.get("name", "не выбран")) if profile else "не выбран"
        singbox_path = self.singbox.detect_binary(str(self.store.get("singbox_path", ""))) or "не найден"
        text = (
            f"VPN профиль: {name} [{protocol}]\n"
            f"sing-box: {singbox_path}\n"
            "В этом режиме НЕ включайте WireGuard кнопкой во вкладке VPN. sing-box сам читает WireGuard .conf и поднимает VPN внутри TUN. "
            "Если системный WireGuard для этого профиля уже запущен, Cheburnet попробует отключить его перед стартом туннеля.\n"
            "WireGuard .conf работает как точный режим: .ru/.рф/.su и свои правила идут напрямую, финальный трафик идёт в VPN. "
            "YouTube и Discord добавляются в direct, чтобы их продолжал обрабатывать zapret."
        )
        tk.Label(
            top,
            text=text,
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            wraplength=860,
            justify="left",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=18, pady=(8, 16))

        actions = tk.Frame(top, bg=self.colors["surface"])
        actions.pack(fill="x", padx=18, pady=(0, 18))
        self._button(actions, "Скачать sing-box", self._download_singbox).pack(side="left", padx=(0, 8))
        self._button(actions, "Сгенерировать конфиг", self._generate_rule_config).pack(side="left", padx=8)
        self._button(actions, "Проверить конфиг", self._check_rule_config).pack(side="left", padx=8)
        self._button(actions, "Запустить туннель", self._start_rule_tunnel).pack(side="left", padx=8)
        self._button(actions, "Остановить", self._stop_rule_tunnel, danger=True).pack(side="left", padx=8)

        middle = tk.Frame(frame, bg=self.colors["bg"])
        middle.pack(fill="both", expand=True)
        rules_card = self._card(middle)
        rules_card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        log_card = self._card(middle)
        log_card.pack(side="left", fill="both", expand=True, padx=(8, 0))

        self._section_title(rules_card, "Как пойдёт трафик")
        details = self._text(rules_card, height=20)
        details.pack(fill="both", expand=True, padx=18, pady=(8, 18))
        details.insert("1.0", self._rule_summary_text())
        details.configure(state="disabled")

        self._section_title(log_card, "Журнал sing-box")
        self.rules_log = self._text(log_card, height=20)
        self.rules_log.pack(fill="both", expand=True, padx=18, pady=(8, 18))
        return frame

    def _whitelist_tab(self) -> tk.Frame:
        frame = self._tab_frame()
        top = self._card(frame)
        top.pack(fill="x", pady=(0, 14))
        self._section_title(top, "Bypass VPN для RU и своих ресурсов")
        note = (
            "CIDR маршрутизируются напрямую через основной шлюз. Домены сначала резолвятся в IPv4. "
            "Суффиксы вроде .ru сохраняются как правило профиля, но для route add их нужно превращать в IP-диапазоны."
        )
        tk.Label(top, text=note, bg=self.colors["surface"], fg=self.colors["muted"], wraplength=900, justify="left").pack(
            anchor="w", padx=18, pady=(4, 14)
        )

        columns = tk.Frame(frame, bg=self.colors["bg"])
        columns.pack(fill="both", expand=True)
        domains_card = self._card(columns)
        domains_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        cidrs_card = self._card(columns)
        cidrs_card.grid(row=0, column=1, sticky="nsew", padx=8)
        apps_card = self._card(columns)
        apps_card.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        columns.columnconfigure(0, weight=3, minsize=260, uniform="whitelist")
        columns.columnconfigure(1, weight=3, minsize=260, uniform="whitelist")
        columns.columnconfigure(2, weight=2, minsize=280)
        columns.rowconfigure(0, weight=1)

        self._section_title(domains_card, "Домены")
        self.domains_text = self._text(domains_card, height=18)
        self.domains_text.pack(fill="both", expand=True, padx=18, pady=(8, 18))
        self.domains_text.insert("1.0", "\n".join(self.store.get("bypass_domains", [])))

        self._section_title(cidrs_card, "CIDR")
        self.cidrs_text = self._text(cidrs_card, height=18)
        self.cidrs_text.pack(fill="both", expand=True, padx=18, pady=(8, 18))
        self.cidrs_text.insert("1.0", "\n".join(self.store.get("bypass_cidrs", [])))

        self._section_title(apps_card, "Приложения")
        self.apps_text = self._text(apps_card, height=14)
        self.apps_text.pack(fill="both", expand=True, padx=18, pady=(8, 8))
        self.apps_text.insert("1.0", "\n".join(self.store.get("bypass_apps", [])))
        tk.Label(
            apps_card,
            text="Список приложений сохраняется, но обычный WireGuard/OpenVPN не умеет per-app маршрутизацию без WFP/TUN-драйвера.",
            bg=self.colors["surface"],
            fg=self.colors["warning"],
            wraplength=360,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 18))

        actions = tk.Frame(frame, bg=self.colors["bg"])
        actions.pack(fill="x", pady=(14, 0))
        self._button(actions, "Сохранить списки", self._save_whitelist).pack(side="left", padx=(0, 8))
        self._button(actions, "Загрузить RU IPv4", self._download_ru_ipv4).pack(side="left", padx=8)
        self._button(actions, "Применить маршруты", self._apply_routes).pack(side="left", padx=8)
        self._button(actions, "Удалить маршруты", self._remove_routes, danger=True).pack(side="left", padx=8)
        return frame

    def _settings_tab(self) -> tk.Frame:
        frame = self._tab_frame()
        card = self._card(frame)
        card.pack(fill="both", expand=True)
        self._section_title(card, "Настройки")
        self._button(card, "Переключить тему", self._toggle_theme).pack(anchor="w", padx=18, pady=(8, 14))

        self.autostart_zapret_var = tk.BooleanVar(value=bool(self.store.get("autostart_zapret", False)))
        self.autostart_vpn_var = tk.BooleanVar(value=bool(self.store.get("autostart_vpn", False)))
        self.autostart_rule_tunnel_var = tk.BooleanVar(value=bool(self.store.get("autostart_rule_tunnel", False)))
        self.route_persistent_var = tk.BooleanVar(value=bool(self.store.get("route_persistent", False)))
        for text, var in [
            ("Запускать лучший zapret при старте приложения", self.autostart_zapret_var),
            ("Подключать выбранный VPN при старте приложения", self.autostart_vpn_var),
            ("Запускать туннель сайтов через sing-box при старте", self.autostart_rule_tunnel_var),
            ("Делать route add постоянным (-p)", self.route_persistent_var),
        ]:
            tk.Checkbutton(
                card,
                text=text,
                variable=var,
                command=self._save_settings_flags,
                bg=self.colors["surface"],
                fg=self.colors["text"],
                activebackground=self.colors["surface"],
                activeforeground=self.colors["text"],
                selectcolor=self.colors["entry"],
                font=("Segoe UI", 10),
            ).pack(anchor="w", padx=18, pady=7)

        info = self._text(card, height=12)
        info.pack(fill="x", padx=18, pady=(18, 12))
        tools = self.vpn.detect_tools()
        info.insert(
            "1.0",
            "\n".join(
                [
                    f"Настройки: {self.store.path}",
                    f"WireGuard: {tools['wireguard'] or 'не найден'}",
                    f"OpenVPN: {tools['openvpn'] or 'не найден'}",
                    f"WARP CLI: {tools['warp'] or 'не найден'}",
                    f"sing-box: {self.singbox.detect_binary(str(self.store.get('singbox_path', ''))) or 'не найден'}",
                    "",
                    "Для route add, WireGuard tunnel service и некоторых функций zapret нужны права администратора.",
                ]
            ),
        )
        info.configure(state="disabled")
        self._button(card, "Открыть папку настроек", lambda: open_folder(self.store.path.parent)).pack(
            anchor="w", padx=18, pady=(0, 18)
        )
        return frame

    # TAB_METHODS

    def _tab_frame(self) -> tk.Frame:
        return tk.Frame(self.content, bg=self.colors["bg"])

    def _card(self, master: tk.Misc) -> tk.Frame:
        return tk.Frame(
            master,
            bg=self.colors["surface"],
            highlightbackground=self.colors["line"],
            highlightthickness=1,
        )

    def _section_title(self, master: tk.Misc, text: str) -> None:
        tk.Label(
            master,
            text=text,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            font=("Segoe UI Semibold", 14),
        ).pack(anchor="w", padx=18, pady=(16, 0))

    def _button(
        self,
        master: tk.Misc,
        text: str,
        command: Callable[[], None],
        *,
        danger: bool = False,
        flat: bool = False,
    ) -> tk.Button:
        bg = self.colors["surface2"] if flat else self.colors["accent2"]
        fg = self.colors["text"] if flat else "#ffffff"
        if danger:
            bg = self.colors["danger"]
            fg = "#ffffff"
        return tk.Button(
            master,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=self.colors["accent"],
            activeforeground="#ffffff",
            relief="flat",
            padx=12,
            pady=8,
            borderwidth=0,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
        )

    def _entry(self, master: tk.Misc, variable: tk.StringVar) -> tk.Entry:
        return tk.Entry(
            master,
            textvariable=variable,
            bg=self.colors["entry"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors["line"],
            font=("Segoe UI", 10),
        )

    def _text(self, master: tk.Misc, height: int) -> tk.Text:
        return tk.Text(
            master,
            height=height,
            bg=self.colors["entry"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.colors["line"],
            font=("Consolas", 10),
            wrap="word",
        )

    def _show_tab(self, key: str) -> None:
        self.current_tab = key
        for frame in self.widgets_by_tab.values():
            frame.pack_forget()
        frame = self.widgets_by_tab.get(key)
        if frame:
            frame.pack(fill="both", expand=True)
        for tab_key, button in self.nav_buttons.items():
            if tab_key == key:
                button.configure(bg=self.colors["accent2"], fg="#ffffff")
            else:
                button.configure(bg=self.colors["surface2"], fg=self.colors["text"])

    def _status_text(self) -> str:
        zapret_dir = self.store.get("zapret_dir") or "не выбрана"
        best = self.store.get("best_zapret_config") or "не проверен"
        profiles = self.store.get("vpn_profiles", [])
        singbox = "найден" if self.singbox.detect_binary(str(self.store.get("singbox_path", ""))) else "не найден"
        return "\n".join(
            [
                f"Права администратора: {'есть' if is_admin() else 'нет'}",
                f"Zapret папка: {zapret_dir}",
                f"Лучшая стратегия: {best}",
                f"VPN профилей: {len(profiles)}",
                f"sing-box: {singbox}",
                f"Настройки: {self.store.path}",
            ]
        )

    def _dashboard_note_text(self) -> str:
        if not is_admin():
            return (
                "Сейчас приложение запущено без прав администратора. Для route add, WireGuard tunnel service "
                "и запуска zapret Windows может показать UAC. Тест zapret запрашивает UAC один раз на весь прогон."
            )
        return (
            "Права администратора есть. Можно запускать zapret, применять маршруты обхода VPN и подключать "
            "WireGuard tunnel service без дополнительных запросов UAC."
        )

    def _log(self, message: str, target: tk.Text | None = None) -> None:
        widget = target if target is not None else getattr(self, "log", None)
        if widget is None or not widget.winfo_exists():
            return
        widget.configure(state="normal")
        widget.insert("end", message.rstrip() + "\n")
        widget.see("end")

    def _thread(self, work: Callable[[], None]) -> None:
        thread = threading.Thread(target=work, daemon=True)
        thread.start()

    def _ui_log(self, message: str, target: tk.Text | None = None) -> None:
        self.after(0, lambda: self._log(message, target))

    def _browse_zapret_dir(self) -> None:
        path = filedialog.askdirectory(title="Папка zapret-discord-youtube")
        if not path:
            return
        self.zapret_dir_var.set(path)
        self.store.set("zapret_dir", path)
        self._refresh_configs()

    def _download_zapret(self) -> None:
        destination = filedialog.askdirectory(title="Куда скачать zapret latest release")
        if not destination:
            return

        def work() -> None:
            try:
                root = self.zapret.download_latest_zip(destination, lambda msg: self._ui_log(msg, self.zapret_log))
            except Exception as exc:
                self._ui_log(f"Ошибка скачивания: {exc}", self.zapret_log)
                return
            self.store.set("zapret_dir", str(root))
            self.after(0, lambda: self.zapret_dir_var.set(str(root)))
            self.after(0, self._refresh_configs)
            self._ui_log(f"Готово: {root}", self.zapret_log)

        self._thread(work)

    def _refresh_configs(self) -> None:
        if not hasattr(self, "config_list"):
            return
        path = self.zapret_dir_var.get().strip()
        self.store.set("zapret_dir", path)
        self.config_list.delete(0, "end")
        configs = self.zapret.discover_configs(path) if path else []
        for config in configs:
            self.config_list.insert("end", config.name)
        if configs:
            self._log(f"Найдено стратегий: {len(configs)}", self.zapret_log)
        else:
            self._log("Стратегии не найдены. Укажите папку с service.bat и general*.bat.", self.zapret_log)

    def _selected_zapret_config(self) -> Path | None:
        path = self.zapret_dir_var.get().strip()
        configs = self.zapret.discover_configs(path) if path else []
        selected = self.config_list.curselection() if hasattr(self, "config_list") else []
        if selected and configs:
            return configs[selected[0]]
        best = self.store.get("best_zapret_config")
        for config in configs:
            if config.name == best:
                return config
        return configs[0] if configs else None

    def _start_selected_zapret(self) -> None:
        config = self._selected_zapret_config()
        if not config:
            messagebox.showwarning("Zapret", "Сначала выберите папку и стратегию.")
            return
        try:
            self.zapret.stop_winws()
            self.zapret.start_config(config)
            self.store.set("selected_zapret_config", config.name)
            self._log(f"Запущено: {config.name}", self.zapret_log)
            self._log(f"Zapret запущен: {config.name}")
        except Exception as exc:
            self._log(f"Ошибка запуска: {exc}", self.zapret_log)

    def _start_best_zapret(self) -> None:
        self._start_selected_zapret()

    def _stop_zapret(self) -> None:
        result = self.zapret.stop_winws()
        message = result.text or "winws остановлен или не был запущен."
        if hasattr(self, "zapret_log"):
            self._log(message, self.zapret_log)
        self._log(message)

    def _test_zapret_configs(self) -> None:
        path = self.zapret_dir_var.get().strip()
        if not path:
            messagebox.showwarning("Zapret", "Сначала укажите папку zapret.")
            return
        self.zapret_test_stop.clear()
        self._log("Начинаю проверку всех стратегий. Это может занять несколько минут.", self.zapret_log)

        def work() -> None:
            try:
                results = self.zapret.test_configs_single_admin_prompt(
                    path,
                    progress=lambda msg: self._ui_log(msg, self.zapret_log),
                    stop_event=self.zapret_test_stop,
                )
            except Exception as exc:
                self._ui_log(f"Ошибка проверки: {exc}", self.zapret_log)
                return
            if not results:
                self._ui_log("Проверка не вернула результатов.", self.zapret_log)
                return
            best = results[0]
            self.store.update(
                {
                    "last_zapret_results": [item.to_dict() for item in results],
                    "best_zapret_config": best.config,
                    "selected_zapret_config": best.config,
                }
            )
            self._ui_log(f"Лучший конфиг: {best.config} ({best.score} баллов)", self.zapret_log)
            if hasattr(self, "dashboard_status"):
                self.after(0, lambda: self.dashboard_status.configure(text=self._status_text()))

        self._thread(work)

    def _render_profiles(self) -> None:
        if not hasattr(self, "profile_list"):
            return
        self.profile_list.delete(0, "end")
        for profile in self.store.get("vpn_profiles", []):
            self.profile_list.insert("end", f"{profile.get('name')} [{profile.get('protocol')}]")

    def _selected_profile(self) -> dict[str, object] | None:
        profiles = self.store.get("vpn_profiles", [])
        selected = self.profile_list.curselection() if hasattr(self, "profile_list") else []
        if selected and profiles:
            return profiles[selected[0]]
        selected_id = self.store.get("selected_vpn_profile")
        for profile in profiles:
            if profile.get("id") == selected_id:
                return profile
        return profiles[0] if profiles else None

    def _selected_profile_from_store(self) -> dict[str, object] | None:
        profiles = self.store.get("vpn_profiles", [])
        selected_id = self.store.get("selected_vpn_profile")
        for profile in profiles:
            if profile.get("id") == selected_id:
                return profile
        return profiles[0] if profiles else None

    def _add_profile(self, protocol: str, path: str = "") -> None:
        profile = self.vpn.make_profile(protocol, path)
        profiles = list(self.store.get("vpn_profiles", []))
        profiles = [item for item in profiles if item.get("id") != profile["id"]]
        profiles.append(profile)
        self.store.update({"vpn_profiles": profiles, "selected_vpn_profile": profile["id"]})
        self._render_profiles()
        self._log(f"Добавлен VPN профиль: {profile['name']}", self.vpn_status)

    def _import_wireguard(self) -> None:
        path = filedialog.askopenfilename(
            title="WireGuard .conf",
            filetypes=[("WireGuard config", "*.conf"), ("All files", "*.*")],
        )
        if path:
            self._add_profile("wireguard", path)

    def _import_openvpn(self) -> None:
        path = filedialog.askopenfilename(
            title="OpenVPN .ovpn",
            filetypes=[("OpenVPN config", "*.ovpn"), ("All files", "*.*")],
        )
        if path:
            self._add_profile("openvpn", path)

    def _add_warp_profile(self) -> None:
        self._add_profile("warp", "")

    def _connect_vpn(self) -> None:
        profile = self._selected_profile()
        if not profile:
            messagebox.showwarning("VPN", "Сначала добавьте VPN профиль.")
            return
        if str(profile.get("protocol", "")).lower() == "wireguard":
            proceed = messagebox.askyesno(
                "Системный WireGuard",
                "Эта кнопка включает обычный full-tunnel WireGuard через Windows. "
                "Для схемы `.ru напрямую, остальное через VPN` используйте вкладку `Туннель сайтов`, "
                "а не системное подключение WireGuard.\n\nВсё равно включить системный WireGuard?",
            )
            if not proceed:
                self._show_tab("rules")
                return
        self.store.set("selected_vpn_profile", profile.get("id", ""))

        def work() -> None:
            result = self.vpn.connect(profile)
            self._ui_log(result.message, self.vpn_status)
            self._ui_log(result.message)

        self._thread(work)

    def _disconnect_vpn(self) -> None:
        profile = self._selected_profile()
        if not profile:
            return

        def work() -> None:
            result = self.vpn.disconnect(profile)
            self._ui_log(result.message, self.vpn_status)
            self._ui_log(result.message)

        self._thread(work)

    def _remove_vpn_profile(self) -> None:
        selected = self.profile_list.curselection() if hasattr(self, "profile_list") else []
        if not selected:
            return
        profiles = list(self.store.get("vpn_profiles", []))
        removed = profiles.pop(selected[0])
        self.store.update({"vpn_profiles": profiles, "selected_vpn_profile": ""})
        self._render_profiles()
        self._log(f"Удалён профиль: {removed.get('name')}", self.vpn_status)

    def _refresh_vpn_status(self) -> None:
        if not hasattr(self, "vpn_status"):
            return
        self.vpn_status.configure(state="normal")
        self.vpn_status.delete("1.0", "end")
        self.vpn_status.insert("1.0", self.vpn.status())

    def _install_vpn_component(self, component: str) -> None:
        def work() -> None:
            result = self.vpn.download_and_run_installer(component, lambda msg: self._ui_log(msg, self.vpn_status))
            self._ui_log(result.message, self.vpn_status)
            self._ui_log(result.message)

        self._thread(work)

    def _selected_rule_profile(self) -> dict[str, object] | None:
        selected = self._selected_profile_from_store()
        if selected and str(selected.get("protocol", "")).lower() == "wireguard":
            return selected
        for profile in self.store.get("vpn_profiles", []):
            if str(profile.get("protocol", "")).lower() == "wireguard":
                return profile
        return selected

    def _rule_summary_text(self) -> str:
        domains = self.store.get("bypass_domains", [])
        cidrs = self.store.get("bypass_cidrs", [])
        apps = self.store.get("bypass_apps", [])
        return "\n".join(
            [
                "DIRECT, мимо VPN:",
                "- suffix: .ru, .рф, .su и всё, что добавлено в белый список доменов",
                "- YouTube / Discord / GoogleVideo / Discord CDN для работы через zapret",
                f"- CIDR правил: {len(cidrs)}",
                f"- приложений в direct-списке: {len(apps)}",
                "",
                "VPN:",
                "- финальное правило final -> WireGuard outbound",
                "- всё, что не совпало с DIRECT-правилами",
                "",
                "Текущие домены:",
                *(f"- {domain}" for domain in domains[:80]),
                *([f"... ещё {len(domains) - 80}"] if len(domains) > 80 else []),
            ]
        )

    def _sync_whitelist_widgets(self) -> None:
        if hasattr(self, "domains_text") and hasattr(self, "cidrs_text") and hasattr(self, "apps_text"):
            self._save_whitelist()

    def _download_singbox(self) -> None:
        def work() -> None:
            try:
                path = self.singbox.download_latest(lambda msg: self._ui_log(msg, self.rules_log))
            except Exception as exc:
                self._ui_log(f"Ошибка скачивания sing-box: {exc}", self.rules_log)
                return
            self.store.set("singbox_path", str(path))
            self._ui_log(f"sing-box установлен: {path}", self.rules_log)

        self._thread(work)

    def _build_rule_config(self, show_warnings: bool = True) -> Path | None:
        self._sync_whitelist_widgets()
        profile = self._selected_rule_profile()
        if not profile:
            if show_warnings:
                messagebox.showwarning("Туннель сайтов", "Сначала добавьте WireGuard профиль во вкладке VPN.")
            return None
        if str(profile.get("protocol", "")).lower() != "wireguard":
            if show_warnings:
                messagebox.showwarning(
                    "Туннель сайтов",
                    "Точный доменный режим доступен для WireGuard .conf. OpenVPN остаётся системным VPN-профилем.",
                )
            return None
        try:
            path = self.singbox.generate_config(
                profile,
                self.store.get("bypass_domains", []),
                self.store.get("bypass_cidrs", []),
                self.store.get("bypass_apps", []),
            )
        except Exception as exc:
            self._log(f"Ошибка генерации sing-box: {exc}", self.rules_log)
            return None
        self.store.set("last_singbox_config", str(path))
        return path

    def _generate_rule_config(self) -> None:
        path = self._build_rule_config(show_warnings=True)
        if not path:
            return
        self._log(f"Конфиг sing-box создан: {path}", self.rules_log)

    def _check_rule_config(self) -> None:
        binary = self.singbox.detect_binary(str(self.store.get("singbox_path", "")))
        if not binary:
            messagebox.showwarning("Туннель сайтов", "Сначала скачайте sing-box.")
            return
        config_path = self.store.get("last_singbox_config") or str(self.singbox.default_config_path())
        if not Path(config_path).exists():
            generated = self._build_rule_config(show_warnings=True)
            if not generated:
                return
            config_path = str(generated)

        def work() -> None:
            result = self.singbox.check_config(binary, config_path)
            text = result.text or ("Конфиг корректен." if result.ok else "sing-box check вернул ошибку.")
            self._ui_log(text, self.rules_log)

        self._thread(work)

    def _start_rule_tunnel(self) -> None:
        binary = self.singbox.detect_binary(str(self.store.get("singbox_path", "")))
        if not binary:
            messagebox.showwarning("Туннель сайтов", "Сначала скачайте sing-box.")
            return
        profile = self._selected_rule_profile()
        if not profile:
            messagebox.showwarning("Туннель сайтов", "Сначала добавьте WireGuard профиль во вкладке VPN.")
            return
        generated = self._build_rule_config(show_warnings=True)
        if not generated:
            return
        config_path = str(generated)

        def work() -> None:
            check = self.singbox.check_config(binary, config_path)
            if not check.ok:
                self._ui_log(check.text or "sing-box check не прошёл.", self.rules_log)
                return
            if str(profile.get("protocol", "")).lower() == "wireguard":
                stopped = self.vpn.disconnect(profile)
                if stopped.ok:
                    self._ui_log("Системный WireGuard для этого профиля отключён перед запуском sing-box.", self.rules_log)
            result = self.singbox.start(binary, config_path)
            self._ui_log(result.message, self.rules_log)
            self._ui_log(result.message)

        self._thread(work)

    def _stop_rule_tunnel(self) -> None:
        def work() -> None:
            result = self.singbox.stop()
            self._ui_log(result.message, self.rules_log)
            self._ui_log(result.message)

        self._thread(work)

    def _read_text_lines(self, widget: tk.Text) -> list[str]:
        return [
            line.strip()
            for line in widget.get("1.0", "end").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    def _save_whitelist(self) -> None:
        domains = self._read_text_lines(self.domains_text)
        cidrs = self._read_text_lines(self.cidrs_text)
        apps = self._read_text_lines(self.apps_text)
        self.store.update({"bypass_domains": domains, "bypass_cidrs": cidrs, "bypass_apps": apps})
        self._log("Белые списки сохранены.")

    def _download_ru_ipv4(self) -> None:
        def work() -> None:
            try:
                cidrs = self.routes.download_ru_ipv4(lambda msg: self._ui_log(msg))
            except Exception as exc:
                self._ui_log(f"Не удалось загрузить RU IPv4: {exc}")
                return
            self.store.set("bypass_cidrs", cidrs)

            def update_text() -> None:
                self.cidrs_text.delete("1.0", "end")
                self.cidrs_text.insert("1.0", "\n".join(cidrs))

            self.after(0, update_text)
            self._ui_log(f"RU IPv4 загружены: {len(cidrs)} сетей.")

        self._thread(work)

    def _apply_routes(self) -> None:
        self._save_whitelist()
        domains = self.store.get("bypass_domains", [])
        cidrs = self.store.get("bypass_cidrs", [])
        persistent = bool(self.store.get("route_persistent", False))

        def work() -> None:
            try:
                targets = self.routes.resolve_targets(domains, cidrs, lambda msg: self._ui_log(msg))
                self._ui_log(f"Готово целей для route add: {len(targets)}")
                applied = self.routes.apply_routes(targets, persistent=persistent, progress=lambda msg: self._ui_log(msg))
            except Exception as exc:
                self._ui_log(f"Не удалось применить маршруты: {exc}")
                return
            self.store.set("last_applied_routes", self.routes.targets_to_dicts(applied))
            self._ui_log(f"Маршруты применены: {len(applied)}")

        self._thread(work)

    def _remove_routes(self) -> None:
        values = self.store.get("last_applied_routes", [])
        targets = self.routes.dicts_to_targets(values)

        def work() -> None:
            self.routes.remove_routes(targets, lambda msg: self._ui_log(msg))
            self.store.set("last_applied_routes", [])
            self._ui_log("Список применённых маршрутов очищен.")

        self._thread(work)

    def _toggle_theme(self) -> None:
        next_theme = "light" if self.theme_name == "dark" else "dark"
        self.store.set("theme", next_theme)
        self.theme_name = next_theme
        self.colors = THEMES[next_theme]
        geometry = self.geometry()
        for child in self.winfo_children():
            child.destroy()
        self.geometry(geometry)
        self._configure_style()
        self._build_layout()

    def _save_settings_flags(self) -> None:
        self.store.update(
            {
                "autostart_zapret": bool(self.autostart_zapret_var.get()),
                "autostart_vpn": bool(self.autostart_vpn_var.get()),
                "autostart_rule_tunnel": bool(self.autostart_rule_tunnel_var.get()),
                "route_persistent": bool(self.route_persistent_var.get()),
            }
        )

    def _maybe_autostart(self) -> None:
        if bool(self.store.get("autostart_zapret", False)):
            self._start_best_zapret()
        if bool(self.store.get("autostart_vpn", False)):
            self._connect_vpn()
        if bool(self.store.get("autostart_rule_tunnel", False)):
            self._start_rule_tunnel()

    def _on_close(self) -> None:
        if self.is_closing:
            return
        self.is_closing = True
        self.store.set("window_geometry", self.geometry())
        self._set_closing_state()

        def work() -> None:
            try:
                self.zapret_test_stop.set()
                self.zapret.stop_winws()
                self.singbox.stop()
                profile = self._selected_profile_from_store()
                if profile:
                    self.vpn.disconnect(profile)
            finally:
                self.after(0, self.destroy)

        self._thread(work)

    def _set_closing_state(self) -> None:
        self.title("Cheburnet - закрытие")
        for button in self.nav_buttons.values():
            button.configure(state="disabled")
        if hasattr(self, "log") and self.log.winfo_exists():
            self._log("Закрытие: останавливаю zapret, туннель сайтов и VPN...")

    @staticmethod
    def _blend(a: str, b: str, ratio: float) -> str:
        ax = tuple(int(a[i : i + 2], 16) for i in (1, 3, 5))
        bx = tuple(int(b[i : i + 2], 16) for i in (1, 3, 5))
        mixed = tuple(round(ax[i] + (bx[i] - ax[i]) * ratio) for i in range(3))
        return "#{:02x}{:02x}{:02x}".format(*mixed)

    # HELPER_METHODS


def main() -> None:
    enable_dpi_awareness()
    app = CheburnetApp()
    app.mainloop()
