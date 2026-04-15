from __future__ import annotations

import math
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from cheburnet.config import SettingsStore
from cheburnet.controllers.routes import RouteManager
from cheburnet.controllers.singbox import SingBoxController
from cheburnet.controllers.system import IS_WINDOWS, enable_dpi_awareness, is_admin, open_folder, run_command
from cheburnet.controllers.vpn import VpnController
from cheburnet.controllers.zapret import ZapretController

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except ImportError:  # pragma: no cover - graceful fallback for source runs without Pillow
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageTk = None


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
        self.ui_images: list[tk.PhotoImage] = []
        self.image_cache: dict[str, tk.PhotoImage] = {}
        self.responsive_labels: list[tuple[tk.Widget, tk.Misc, int]] = []
        self.settings_grid: tk.Frame | None = None
        self.settings_left: tk.Frame | None = None
        self.settings_right: tk.Frame | None = None
        self.settings_stacked = False
        self.gradient_phase = 0.0
        self.header_generation = 0
        self.zapret_test_stop = threading.Event()
        self.is_closing = False
        self.status_refresh_job: str | None = None
        self.title("Cheburnet")
        self._apply_window_icon()
        self.geometry(str(self.store.get("window_geometry", "1180x760")))
        self.minsize(760, 560)
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._configure_style()
        self._build_layout()
        self.after(600, self._maybe_show_onboarding)
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
        self.ui_images = []
        self.image_cache = {}
        self.responsive_labels = []
        self.settings_grid = None
        self.settings_left = None
        self.settings_right = None
        self.settings_stacked = False
        self.root_frame = tk.Frame(self, bg=self.colors["bg"])
        self.root_frame.pack(fill="both", expand=True)

        self.main = tk.Frame(self.root_frame, bg=self.colors["bg"])
        self.main.pack(fill="both", expand=True)

        self.content = tk.Frame(self.main, bg=self.colors["bg"])
        self.content.pack(fill="both", expand=True, padx=28, pady=24)

        self.widgets_by_tab = {
            "dashboard": self._dashboard_tab(),
            "settings": self._settings_tab(),
        }
        self._show_tab(self.current_tab)
        self.after(800, self._refresh_main_status)

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
            text="Простая настройка интернета",
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
            ("guide", "Гайд"),
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
        top = tk.Frame(frame, bg=self.colors["bg"])
        top.pack(fill="x")

        title_box = tk.Frame(top, bg=self.colors["bg"])
        title_box.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_box,
            text="CheburNet",
            bg=self.colors["bg"],
            fg=self.colors["text"],
            font=("Segoe UI Semibold", 34),
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text="Три режима. Включите нужный, приложение подскажет остальное.",
            bg=self.colors["bg"],
            fg=self.colors["muted"],
            font=("Segoe UI", 12),
        ).pack(anchor="w", pady=(4, 0))

        self._gear_button(top).pack(side="right", padx=(16, 0), pady=(4, 0))

        modes = tk.Frame(frame, bg=self.colors["bg"])
        modes.pack(fill="both", expand=True, pady=(34, 18))
        modes.columnconfigure(0, weight=1)
        self.mode_switches: dict[str, tk.Label] = {}
        self.mode_status_labels: dict[str, tk.Label] = {}

        rows = [
            (
                "zapret",
                "YouTube и Discord",
                "Для YouTube и Discord. Остальной интернет не трогаем.",
            ),
            (
                "vpn",
                "VPN",
                "Весь интернет через выбранный VPN.",
            ),
            (
                "tunnel",
                "Туннелирование",
                "Российские сайты напрямую, остальные через VPN.",
            ),
        ]
        for index, (key, title, description) in enumerate(rows):
            row = self._mode_row(modes, key, title, description)
            row.grid(row=index, column=0, sticky="ew", pady=8)
        modes.bind("<Configure>", lambda _event: self._update_responsive_text())

        footer = tk.Frame(frame, bg=self.colors["bg"])
        footer.pack(fill="x")
        self.dashboard_status = tk.Label(
            footer,
            text="",
            bg=self.colors["bg"],
            fg=self.colors["muted"],
            justify="left",
            font=("Segoe UI", 10),
        )
        self.dashboard_status.pack(side="left", anchor="w")
        self.log = self._text(footer, height=3)
        self.log.pack(side="right", fill="x", expand=True, padx=(18, 0))
        self._log("Готово. Выберите режим на главном экране.")
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
            text="Если используете 'Туннель сайтов', кнопку 'Подключить системный VPN' обычно включать не нужно.",
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
            "Этот режим помогает пустить часть сайтов напрямую, а остальное через VPN.\n"
            "Обычно достаточно: выбрать WireGuard .conf -> сгенерировать конфиг -> запустить туннель."
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
            "Здесь можно указать сайты и сети, которые должны идти напрямую (мимо VPN). "
            "Если не уверены, оставьте значения по умолчанию."
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
            text="Список приложений сохраняется для режима 'Туннель сайтов'.",
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
        top = tk.Frame(frame, bg=self.colors["bg"])
        top.pack(fill="x", pady=(0, 18))
        self._button(top, "Назад", lambda: self._show_tab("dashboard"), flat=True).pack(side="left")
        tk.Label(
            top,
            text="Настройки",
            bg=self.colors["bg"],
            fg=self.colors["text"],
            font=("Segoe UI Semibold", 24),
        ).pack(side="left", padx=14)
        self._button(top, "Светлая/тёмная тема", self._toggle_theme).pack(side="right")

        grid = tk.Frame(frame, bg=self.colors["bg"])
        grid.pack(fill="both", expand=True)
        self.settings_grid = grid
        grid.columnconfigure(0, weight=1, uniform="settings")
        grid.columnconfigure(1, weight=1, uniform="settings")
        grid.rowconfigure(0, weight=1)

        left = tk.Frame(grid, bg=self.colors["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = tk.Frame(grid, bg=self.colors["bg"])
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.settings_left = left
        self.settings_right = right
        grid.bind("<Configure>", lambda _event: self._update_settings_layout())

        zapret_card = self._card(left)
        zapret_card.pack(fill="both", expand=True, pady=(0, 12))
        self._section_title(zapret_card, "YouTube и Discord")
        self.zapret_dir_var = tk.StringVar(value=str(self.store.get("zapret_dir", "")))
        path_row = tk.Frame(zapret_card, bg=self.colors["surface"])
        path_row.pack(fill="x", padx=18, pady=(10, 10))
        self._entry(path_row, self.zapret_dir_var).pack(side="left", fill="x", expand=True)
        self._button(path_row, "Папка", self._browse_zapret_dir).pack(side="left", padx=(8, 0))
        self._button(path_row, "Скачать", self._download_zapret).pack(side="left", padx=(8, 0))
        self.config_list = tk.Listbox(
            zapret_card,
            height=6,
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
        self.config_list.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        zapret_actions = tk.Frame(zapret_card, bg=self.colors["surface"])
        zapret_actions.pack(fill="x", padx=18, pady=(0, 18))
        self._button(zapret_actions, "Использовать", self._use_selected_zapret_config).pack(side="left", padx=(0, 8))
        self._button(zapret_actions, "Проверить все", self._test_zapret_configs).pack(side="left", padx=8)
        self._button(zapret_actions, "Остановить", self._stop_zapret, danger=True).pack(side="left", padx=8)

        vpn_card = self._card(left)
        vpn_card.pack(fill="both", expand=True)
        self._section_title(vpn_card, "VPN")
        self.profile_list = tk.Listbox(
            vpn_card,
            height=6,
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
        self.profile_list.pack(fill="both", expand=True, padx=18, pady=(10, 10))
        vpn_actions = tk.Frame(vpn_card, bg=self.colors["surface"])
        vpn_actions.pack(fill="x", padx=18, pady=(0, 10))
        self._button(vpn_actions, "WireGuard", self._import_wireguard).pack(side="left", padx=(0, 8))
        self._button(vpn_actions, "OpenVPN", self._import_openvpn).pack(side="left", padx=8)
        self._button(vpn_actions, "WARP", self._add_warp_profile).pack(side="left", padx=8)
        vpn_use = tk.Frame(vpn_card, bg=self.colors["surface"])
        vpn_use.pack(fill="x", padx=18, pady=(0, 18))
        self._button(vpn_use, "Использовать", self._use_selected_vpn_profile).pack(side="left", padx=(0, 8))
        self._button(vpn_use, "Удалить", self._remove_vpn_profile, danger=True).pack(side="left", padx=8)
        self._button(vpn_use, "Скачать VPN", self._open_vpn_setup).pack(side="left", padx=8)

        tunnel_card = self._card(right)
        tunnel_card.pack(fill="x", pady=(0, 12))
        self._section_title(tunnel_card, "Тунелирование")
        tk.Label(
            tunnel_card,
            text="В этом списке сайты идут напрямую. Всё остальное пойдёт через выбранный VPN.",
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            wraplength=430,
            justify="left",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=18, pady=(10, 12))
        tunnel_actions = tk.Frame(tunnel_card, bg=self.colors["surface"])
        tunnel_actions.pack(fill="x", padx=18, pady=(0, 18))
        self._button(tunnel_actions, "Открыть список сайтов", self._open_direct_sites_file).pack(side="left", padx=(0, 8))
        self._button(tunnel_actions, "Скачать sing-box", self._download_singbox).pack(side="left", padx=8)
        self._button(tunnel_actions, "Остановить", self._stop_rule_tunnel, danger=True).pack(side="left", padx=8)

        common_card = self._card(right)
        common_card.pack(fill="x", pady=(0, 12))
        self._section_title(common_card, "Запуск")
        self.autostart_zapret_var = tk.BooleanVar(value=bool(self.store.get("autostart_zapret", False)))
        self.autostart_vpn_var = tk.BooleanVar(value=bool(self.store.get("autostart_vpn", False)))
        self.autostart_rule_tunnel_var = tk.BooleanVar(value=bool(self.store.get("autostart_rule_tunnel", False)))
        self.route_persistent_var = tk.BooleanVar(value=bool(self.store.get("route_persistent", False)))
        for text, var in [
            ("Включать YouTube и Discord при старте", self.autostart_zapret_var),
            ("Включать VPN при старте", self.autostart_vpn_var),
            ("Включать туннелирование при старте", self.autostart_rule_tunnel_var),
        ]:
            tk.Checkbutton(
                common_card,
                text=text,
                variable=var,
                command=self._save_settings_flags,
                bg=self.colors["surface"],
                fg=self.colors["text"],
                activebackground=self.colors["surface"],
                activeforeground=self.colors["text"],
                selectcolor=self.colors["entry"],
                font=("Segoe UI", 10),
            ).pack(anchor="w", padx=18, pady=5)
        common_actions = tk.Frame(common_card, bg=self.colors["surface"])
        common_actions.pack(fill="x", padx=18, pady=(8, 18))
        self._button(common_actions, "Показать гайд", lambda: self._open_onboarding(force=True)).pack(side="left", padx=(0, 8))
        self._button(common_actions, "Папка настроек", lambda: open_folder(self.store.path.parent)).pack(side="left", padx=8)

        log_card = self._card(right)
        log_card.pack(fill="both", expand=True)
        self._section_title(log_card, "Последние действия")
        self.service_log = self._text(log_card, height=8)
        self.service_log.pack(fill="both", expand=True, padx=18, pady=(10, 18))
        self.zapret_log = self.service_log
        self.vpn_status = self.service_log
        self.rules_log = self.service_log
        self._ensure_direct_sites_file()
        self._refresh_configs()
        self._render_profiles()
        return frame

    def _guide_tab(self) -> tk.Frame:
        frame = self._tab_frame()
        card = self._card(frame)
        card.pack(fill="both", expand=True)
        self._section_title(card, "Гайд: с чего начать")

        text = self._text(card, height=16)
        text.pack(fill="x", padx=18, pady=(8, 12))
        text.insert(
            "1.0",
            "\n".join(
                [
                    "1) YouTube / Discord",
                    "- Выберите папку zapret или нажмите 'Скачать latest'.",
                    "- Нажмите 'Тест всех', затем 'Запуск'.",
                    "",
                    "2) VPN",
                    "- Импортируйте WireGuard .conf (или OpenVPN .ovpn).",
                    "",
                    "3) Туннель сайтов (по желанию)",
                    "- Нажмите 'Скачать sing-box'.",
                    "- Нажмите 'Сгенерировать конфиг' и 'Запустить туннель'.",
                    "",
                    "Если не уверены, просто идите по шагам сверху вниз.",
                ]
            ),
        )
        text.configure(state="disabled")

        actions = tk.Frame(card, bg=self.colors["surface"])
        actions.pack(fill="x", padx=18, pady=(0, 18))
        self._button(actions, "Открыть YouTube / Discord", lambda: self._show_tab("zapret")).pack(side="left", padx=(0, 8))
        self._button(actions, "Открыть VPN", lambda: self._show_tab("vpn")).pack(side="left", padx=8)
        self._button(actions, "Открыть Туннель сайтов", lambda: self._show_tab("rules")).pack(side="left", padx=8)
        self._button(actions, "Показать гайд первого запуска", lambda: self._open_onboarding(force=True)).pack(
            side="left", padx=8
        )
        return frame

    # TAB_METHODS

    def _mode_row(self, master: tk.Misc, key: str, title: str, description: str) -> tk.Frame:
        row = self._card(master)
        row.columnconfigure(0, weight=1)

        text_box = tk.Frame(row, bg=self.colors["surface"])
        text_box.grid(row=0, column=0, sticky="nsew", padx=22, pady=18)
        tk.Label(
            text_box,
            text=title,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            font=("Segoe UI Semibold", 17),
        ).pack(anchor="w")
        description_label = tk.Label(
            text_box,
            text=description,
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            font=("Segoe UI", 11),
            wraplength=620,
            justify="left",
        )
        description_label.pack(anchor="w", pady=(5, 0))
        self.responsive_labels.append((description_label, row, 150))
        status = tk.Label(
            text_box,
            text="",
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        )
        status.pack(anchor="w", pady=(10, 0))
        self.mode_status_labels[key] = status

        switch = tk.Label(row, bg=self.colors["surface"], borderwidth=0, cursor="hand2")
        switch.grid(row=0, column=1, padx=22, pady=18)
        switch.bind("<Button-1>", lambda _event, mode=key: self._toggle_mode(mode))
        self.mode_switches[key] = switch
        self._draw_switch(switch, False)
        return row

    def _gear_button(self, master: tk.Misc) -> tk.Label:
        button = tk.Label(master, bg=self.colors["bg"], borderwidth=0, cursor="hand2")
        button.configure(image=self._make_gear_image())
        button.bind("<Button-1>", lambda _event: self._show_tab("settings"))
        return button

    def _draw_switch(self, widget: tk.Label, enabled: bool) -> None:
        widget.configure(image=self._make_switch_image(enabled))

    def _make_switch_image(self, enabled: bool) -> tk.PhotoImage:
        cache_key = f"switch:{self.theme_name}:{enabled}"
        if cache_key in self.image_cache:
            return self.image_cache[cache_key]
        if Image is None or ImageDraw is None or ImageTk is None:
            image = tk.PhotoImage(width=74, height=40)
            image.put(self.colors["accent"] if enabled else self.colors["surface2"], to=(0, 0, 74, 40))
            self.ui_images.append(image)
            self.image_cache[cache_key] = image
            return image
        scale = 4
        width, height = 74, 40
        image = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        track = self.colors["accent"] if enabled else self.colors["surface2"]
        outline = self._blend(track, self.colors["line"], 0.28)
        shadow = (0, 0, 0, 46) if self.theme_name == "light" else (0, 0, 0, 82)
        draw.rounded_rectangle((2 * scale, 4 * scale, (width - 2) * scale, (height - 1) * scale), radius=19 * scale, fill=shadow)
        draw.rounded_rectangle((1 * scale, 1 * scale, (width - 1) * scale, (height - 4) * scale), radius=19 * scale, fill=track, outline=outline, width=1 * scale)
        knob_x = 40 if enabled else 6
        draw.ellipse((knob_x * scale, 6 * scale, (knob_x + 28) * scale, 34 * scale), fill="#ffffff", outline=(0, 0, 0, 28), width=1 * scale)
        small = image.resize((width, height), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(small)
        self.ui_images.append(photo)
        self.image_cache[cache_key] = photo
        return photo

    def _make_gear_image(self) -> tk.PhotoImage:
        cache_key = f"gear:{self.theme_name}"
        if cache_key in self.image_cache:
            return self.image_cache[cache_key]
        if Image is None or ImageDraw is None or ImageTk is None:
            image = tk.PhotoImage(width=52, height=52)
            self.image_cache[cache_key] = image
            return image
        scale = 4
        size = 52
        image = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((3 * scale, 3 * scale, 49 * scale, 49 * scale), fill=self.colors["surface"], outline=self.colors["line"], width=1 * scale)
        text = "\u2699"
        font = self._gear_font(28 * scale)
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (size * scale - (bbox[2] - bbox[0])) / 2 - bbox[0]
        y = (size * scale - (bbox[3] - bbox[1])) / 2 - bbox[1] - 1 * scale
        draw.text((x, y), text, fill=self.colors["text"], font=font)
        small = image.resize((size, size), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(small)
        self.ui_images.append(photo)
        self.image_cache[cache_key] = photo
        return photo

    def _gear_font(self, size: int):
        if ImageFont is None:
            return None
        for path in [
            r"C:\Windows\Fonts\seguisym.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arial.ttf",
        ]:
            if Path(path).exists():
                try:
                    return ImageFont.truetype(path, size=size)
                except OSError:
                    pass
        return ImageFont.load_default()

    def _update_responsive_text(self) -> None:
        for label, container, reserve in self.responsive_labels:
            if not label.winfo_exists() or not container.winfo_exists():
                continue
            width = max(container.winfo_width() - reserve, 220)
            try:
                label.configure(wraplength=width)
            except tk.TclError:
                pass

    def _update_settings_layout(self) -> None:
        if not self.settings_grid or not self.settings_left or not self.settings_right:
            return
        if not self.settings_grid.winfo_exists():
            return
        width = self.settings_grid.winfo_width()
        should_stack = width < 900
        if should_stack == self.settings_stacked:
            return
        self.settings_stacked = should_stack
        if should_stack:
            self.settings_grid.columnconfigure(0, weight=1, uniform="")
            self.settings_grid.columnconfigure(1, weight=0, uniform="")
            self.settings_grid.rowconfigure(0, weight=0)
            self.settings_grid.rowconfigure(1, weight=1)
            self.settings_left.grid_configure(row=0, column=0, sticky="nsew", padx=0, pady=(0, 12))
            self.settings_right.grid_configure(row=1, column=0, sticky="nsew", padx=0, pady=0)
        else:
            self.settings_grid.columnconfigure(0, weight=1, uniform="settings")
            self.settings_grid.columnconfigure(1, weight=1, uniform="settings")
            self.settings_grid.rowconfigure(0, weight=1)
            self.settings_grid.rowconfigure(1, weight=0)
            self.settings_left.grid_configure(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)
            self.settings_right.grid_configure(row=0, column=1, sticky="nsew", padx=(8, 0), pady=0)

    def _toggle_mode(self, mode: str) -> None:
        if mode == "zapret":
            if self._is_zapret_running():
                self._stop_zapret()
            elif self._zapret_ready():
                self._start_selected_zapret()
            else:
                self._open_zapret_setup()
            return
        if mode == "vpn":
            if self._is_vpn_active():
                self._disconnect_vpn()
            else:
                self._turn_on_vpn_from_main()
            return
        if mode == "tunnel":
            if self._is_tunnel_running():
                self._stop_rule_tunnel()
            else:
                self._turn_on_tunnel_from_main()

    def _refresh_main_status(self) -> None:
        if not hasattr(self, "mode_switches"):
            return

        states = {
            "zapret": self._mode_state("zapret"),
            "vpn": self._mode_state("vpn"),
            "tunnel": self._mode_state("tunnel"),
        }
        for key, (enabled, label) in states.items():
            switch = self.mode_switches.get(key)
            if switch and switch.winfo_exists():
                self._draw_switch(switch, enabled)
            status = self.mode_status_labels.get(key)
            if status and status.winfo_exists():
                status.configure(text=label, fg=self.colors["accent"] if enabled else self.colors["muted"])
        if hasattr(self, "dashboard_status") and self.dashboard_status.winfo_exists():
            self.dashboard_status.configure(text=self._friendly_status_text())
        if not self.is_closing:
            if self.status_refresh_job:
                try:
                    self.after_cancel(self.status_refresh_job)
                except tk.TclError:
                    pass
            self.status_refresh_job = self.after(2000, self._refresh_main_status)

    def _mode_state(self, mode: str) -> tuple[bool, str]:
        if mode == "zapret":
            if self._is_zapret_running():
                return True, "Включено"
            return False, "Готово" if self._zapret_ready() else "Нужна настройка"
        if mode == "vpn":
            if self._is_vpn_active():
                profile = self._selected_profile_from_store()
                name = str(profile.get("name", "VPN")) if profile else "VPN"
                return True, f"Включено: {name}"
            return False, "Готово" if self._vpn_ready() else "Нужна настройка"
        if self._is_tunnel_running():
            return True, "Включено"
        return False, "Готово" if self._tunnel_ready() else "Нужна настройка"

    def _friendly_status_text(self) -> str:
        if not is_admin():
            return "Windows может один раз попросить права администратора."
        return "Всё готово к работе."

    def _is_process_running(self, image_name: str) -> bool:
        if not IS_WINDOWS:
            return False
        result = run_command(["tasklist", "/FI", f"IMAGENAME eq {image_name}"], timeout=8)
        return result.ok and image_name.lower() in result.stdout.lower()

    def _is_zapret_running(self) -> bool:
        return self._is_process_running("winws.exe")

    def _is_tunnel_running(self) -> bool:
        process = getattr(self.singbox, "process", None)
        if process and process.poll() is None:
            return True
        return self._is_process_running("sing-box.exe")

    def _is_vpn_active(self) -> bool:
        return bool(self.store.get("vpn_active_profile", ""))

    def _zapret_ready(self) -> bool:
        path = str(self.store.get("zapret_dir", "")).strip()
        return bool(path and self.zapret.discover_configs(path))

    def _vpn_ready(self) -> bool:
        profile = self._selected_profile_from_store()
        return bool(profile and self._profile_tool_available(profile))

    def _tunnel_ready(self) -> bool:
        return bool(self.singbox.detect_binary(str(self.store.get("singbox_path", ""))) and self._selected_rule_profile())

    def _profile_tool_available(self, profile: dict[str, object]) -> bool:
        protocol = str(profile.get("protocol", "")).lower()
        tools = self.vpn.detect_tools()
        if protocol == "warp":
            return bool(tools["warp"])
        if protocol == "wireguard":
            return bool(tools["wireguard"] and Path(str(profile.get("config_path", ""))).exists())
        if protocol == "openvpn":
            return bool(tools["openvpn"] and Path(str(profile.get("config_path", ""))).exists())
        return False

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
        if key not in self.widgets_by_tab:
            key = "settings"
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
        ready = bool(self.store.get("zapret_dir")) and bool(profiles)
        return "\n".join(
            [
                f"Статус: {'почти готово' if ready else 'нужна базовая настройка'}",
                f"Права администратора: {'да' if is_admin() else 'нет'}",
                f"Папка YouTube/Discord: {zapret_dir}",
                f"Лучшая стратегия: {best}",
                f"VPN профилей добавлено: {len(profiles)}",
                f"sing-box: {singbox}",
            ]
        )

    def _dashboard_note_text(self) -> str:
        if not is_admin():
            return (
                "Приложение запущено без прав администратора. Некоторые действия могут попросить подтверждение Windows."
            )
        return (
            "Права администратора есть. Все основные функции доступны без дополнительных запросов."
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

    def _open_zapret_setup(self, parent: tk.Misc | None = None) -> None:
        win = self._setup_window("YouTube и Discord", parent=parent)
        status_var = tk.StringVar(value="Выберите один из вариантов ниже.")
        tk.Label(
            win,
            text="Нужно один раз указать zapret или скачать его автоматически.",
            bg=self.colors["surface"],
            fg=self.colors["text"],
            wraplength=420,
            justify="left",
            font=("Segoe UI", 11),
        ).pack(anchor="w", padx=22, pady=(4, 16))
        tk.Label(
            win,
            textvariable=status_var,
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            wraplength=420,
            justify="left",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=22, pady=(0, 12))

        actions = tk.Frame(win, bg=self.colors["surface"])
        actions.pack(fill="x", padx=22, pady=(0, 16))
        pick_btn = self._button(actions, "Путь до zapret", lambda: self._choose_zapret_from_setup(win, status_var))
        download_btn = self._button(
            actions,
            "Скачать последнюю версию",
            lambda: self._download_zapret_default(win, status_var, [pick_btn, download_btn, settings_btn]),
        )
        settings_btn = self._button(actions, "Открыть настройки", lambda: self._open_settings_from_setup(win), flat=True)
        pick_btn.pack(fill="x", pady=5)
        download_btn.pack(fill="x", pady=5)
        settings_btn.pack(fill="x", pady=5)

    def _choose_zapret_from_setup(self, win: tk.Toplevel, status_var: tk.StringVar | None = None) -> None:
        if status_var is not None:
            status_var.set("Открываю выбор папки...")
        selected = self._pick_zapret_dir(parent=win)
        if not selected:
            if status_var is not None:
                status_var.set("Папка не выбрана.")
            return
        if self._zapret_ready():
            if status_var is not None:
                status_var.set("zapret найден.")
            self._ask_zapret_config_mode(win)
        elif status_var is not None:
            status_var.set("В этой папке не найден zapret. Нужна папка, где есть service.bat и general*.bat.")

    def _download_zapret_default(
        self,
        win: tk.Toplevel | None = None,
        status_var: tk.StringVar | None = None,
        buttons: list[tk.Button] | None = None,
    ) -> None:
        destination = self.store.path.parent / "tools" / "zapret"
        if status_var is not None:
            status_var.set("Скачиваю zapret. Это может занять минуту.")
        for button in buttons or []:
            button.configure(state="disabled")
        self._log("Скачиваю zapret...")

        def work() -> None:
            try:
                root = self.zapret.download_latest_zip(
                    destination,
                    lambda msg: self._ui_zapret_setup_status(status_var, msg),
                )
            except Exception as exc:
                self._ui_zapret_setup_status(status_var, f"Не получилось скачать zapret: {exc}")
                self.after(0, lambda: [button.configure(state="normal") for button in buttons or [] if button.winfo_exists()])
                return
            self.store.set("zapret_dir", str(root))

            def done() -> None:
                for button in buttons or []:
                    if button.winfo_exists():
                        button.configure(state="normal")
                if hasattr(self, "zapret_dir_var"):
                    self.zapret_dir_var.set(str(root))
                self._refresh_configs()
                self._refresh_main_status()
                if status_var is not None:
                    status_var.set("zapret скачан и найден.")
                if win is not None and win.winfo_exists():
                    self._ask_zapret_config_mode(win)

            self.after(0, done)

        self._thread(work)

    def _ui_zapret_setup_status(self, status_var: tk.StringVar | None, message: str) -> None:
        self._ui_log(message, getattr(self, "zapret_log", None))
        if status_var is not None:
            self.after(0, lambda: status_var.set(message))

    def _ask_zapret_config_mode(self, win: tk.Toplevel | None = None) -> None:
        if not self._zapret_ready():
            messagebox.showwarning("YouTube и Discord", "В этой папке не найден zapret.", parent=win or self)
            return
        use_auto = messagebox.askyesno(
            "Выбор настройки",
            "Подобрать лучший вариант автоматически?\n\nДа - приложение проверит варианты само.\nНет - выберете вариант в настройках.",
            parent=win or self,
        )
        if win is not None and win.winfo_exists():
            win.destroy()
        if use_auto:
            self._test_zapret_configs(on_done=self._start_selected_zapret)
        else:
            self._show_tab("settings")

    def _open_vpn_setup(self, parent: tk.Misc | None = None) -> None:
        win = self._setup_window("VPN", parent=parent)
        tools = self.vpn.detect_tools()
        has_tool = any(bool(path) for path in tools.values())
        text = (
            "Сначала установите один VPN-клиент, затем добавьте его конфиг."
            if not has_tool
            else "VPN-клиент найден. Добавьте конфиг или выберите уже добавленный профиль."
        )
        tk.Label(
            win,
            text=text,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            wraplength=420,
            justify="left",
            font=("Segoe UI", 11),
        ).pack(anchor="w", padx=22, pady=(4, 16))

        installs = tk.Frame(win, bg=self.colors["surface"])
        installs.pack(fill="x", padx=22, pady=(0, 12))
        self._button(installs, "Скачать WireGuard", lambda: self._install_vpn_component("wireguard")).pack(fill="x", pady=4)
        self._button(installs, "Скачать OpenVPN", lambda: self._install_vpn_component("openvpn")).pack(fill="x", pady=4)
        self._button(installs, "Скачать WARP", lambda: self._install_vpn_component("warp")).pack(fill="x", pady=4)

        imports = tk.Frame(win, bg=self.colors["surface"])
        imports.pack(fill="x", padx=22, pady=(0, 16))
        self._button(imports, "Добавить WireGuard config", self._import_wireguard).pack(fill="x", pady=4)
        self._button(imports, "Добавить OpenVPN config", self._import_openvpn).pack(fill="x", pady=4)
        self._button(imports, "Добавить WARP", self._add_warp_profile).pack(fill="x", pady=4)
        self._button(imports, "Открыть настройки", lambda: self._open_settings_from_setup(win), flat=True).pack(fill="x", pady=4)

    def _open_tunnel_setup(self, parent: tk.Misc | None = None) -> None:
        win = self._setup_window("Тунелирование", parent=parent)
        tk.Label(
            win,
            text="Для этого режима нужен sing-box и WireGuard-конфиг. Список прямых сайтов можно менять обычным txt-файлом.",
            bg=self.colors["surface"],
            fg=self.colors["text"],
            wraplength=420,
            justify="left",
            font=("Segoe UI", 11),
        ).pack(anchor="w", padx=22, pady=(4, 16))
        actions = tk.Frame(win, bg=self.colors["surface"])
        actions.pack(fill="x", padx=22, pady=(0, 16))
        self._button(actions, "Скачать sing-box", self._download_singbox).pack(fill="x", pady=4)
        self._button(actions, "Добавить WireGuard config", self._import_wireguard).pack(fill="x", pady=4)
        self._button(actions, "Открыть список сайтов", self._open_direct_sites_file).pack(fill="x", pady=4)
        self._button(actions, "Открыть настройки", lambda: self._open_settings_from_setup(win), flat=True).pack(fill="x", pady=4)

    def _setup_window(self, title: str, parent: tk.Misc | None = None) -> tk.Toplevel:
        owner = parent if parent is not None and parent.winfo_exists() else self
        win = tk.Toplevel(owner)
        win._cheburnet_owner = owner  # type: ignore[attr-defined]
        win.title(title)
        win.transient(owner)
        win.resizable(False, False)
        win.configure(bg=self.colors["surface"])
        win.geometry("480x360")
        win.protocol("WM_DELETE_WINDOW", lambda: self._close_setup_window(win))
        tk.Label(
            win,
            text=title,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            font=("Segoe UI Semibold", 20),
        ).pack(anchor="w", padx=22, pady=(20, 8))
        win.update_idletasks()
        self._center_child_window(win, owner)
        win.lift(owner)
        win.focus_force()
        try:
            win.grab_set()
        except tk.TclError:
            pass
        return win

    def _open_settings_from_setup(self, win: tk.Toplevel) -> None:
        owner = getattr(win, "_cheburnet_owner", None)
        try:
            win.grab_release()
        except tk.TclError:
            pass
        if win.winfo_exists():
            win.destroy()
        if owner is not None and owner is not self and owner.winfo_exists():
            try:
                owner.grab_release()
            except tk.TclError:
                pass
            owner.destroy()
        self._show_tab("settings")
        self.lift()
        self.focus_force()

    def _close_setup_window(self, win: tk.Toplevel) -> None:
        owner = getattr(win, "_cheburnet_owner", None)
        try:
            win.grab_release()
        except tk.TclError:
            pass
        if win.winfo_exists():
            win.destroy()
        if owner is not None and owner is not self and owner.winfo_exists():
            try:
                owner.grab_set()
                owner.lift()
                owner.focus_force()
            except tk.TclError:
                pass

    def _center_child_window(self, child: tk.Toplevel, owner: tk.Misc) -> None:
        try:
            owner.update_idletasks()
            child.update_idletasks()
            owner_x = owner.winfo_rootx()
            owner_y = owner.winfo_rooty()
            owner_w = max(owner.winfo_width(), 1)
            owner_h = max(owner.winfo_height(), 1)
            child_w = max(child.winfo_width(), child.winfo_reqwidth())
            child_h = max(child.winfo_height(), child.winfo_reqheight())
            x = owner_x + max((owner_w - child_w) // 2, 0)
            y = owner_y + max((owner_h - child_h) // 2, 0)
            child.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass

    def _turn_on_vpn_from_main(self) -> None:
        if not self._vpn_ready():
            self._open_vpn_setup()
            return
        if self._is_tunnel_running():
            self._stop_rule_tunnel()
        self._connect_vpn()

    def _turn_on_tunnel_from_main(self) -> None:
        if not self.singbox.detect_binary(str(self.store.get("singbox_path", ""))) or not self._selected_rule_profile():
            self._open_tunnel_setup()
            return
        if self._is_vpn_active():
            self._disconnect_vpn()
        self._start_rule_tunnel()

    def _ensure_direct_sites_file(self) -> Path:
        path = self.store.path.parent / "direct-sites.txt"
        if not path.exists():
            domains = self.store.get("bypass_domains", [".ru", ".рф", ".su"])
            path.write_text("\n".join(domains) + "\n", encoding="utf-8")
        return path

    def _load_direct_sites_file(self) -> None:
        path = self._ensure_direct_sites_file()
        lines = [
            line.strip()
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if lines:
            self.store.set("bypass_domains", lines)

    def _open_direct_sites_file(self) -> None:
        path = self._ensure_direct_sites_file()
        try:
            if IS_WINDOWS:
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                open_folder(path.parent)
        except OSError as exc:
            messagebox.showerror("Список сайтов", f"Не получилось открыть файл: {exc}")

    def _browse_zapret_dir(self) -> None:
        self._pick_zapret_dir(parent=self)

    def _pick_zapret_dir(self, parent: tk.Misc | None = None) -> bool:
        path = filedialog.askdirectory(parent=parent, title="Папка zapret-discord-youtube")
        if not path:
            return False
        if hasattr(self, "zapret_dir_var"):
            self.zapret_dir_var.set(path)
        self.store.set("zapret_dir", path)
        self._refresh_configs()
        self._refresh_main_status()
        return True

    def _download_zapret(self) -> None:
        destination = filedialog.askdirectory(title="Куда скачать zapret latest release")
        if not destination:
            return

        def work() -> None:
            try:
                root = self.zapret.download_latest_zip(destination, lambda msg: self._ui_log(msg, getattr(self, "zapret_log", None)))
            except Exception as exc:
                self._ui_log(f"Ошибка скачивания: {exc}", getattr(self, "zapret_log", None))
                return
            self.store.set("zapret_dir", str(root))
            if hasattr(self, "zapret_dir_var"):
                self.after(0, lambda: self.zapret_dir_var.set(str(root)))
            self.after(0, self._refresh_configs)
            self.after(0, self._refresh_main_status)
            self._ui_log(f"Готово: {root}", getattr(self, "zapret_log", None))

        self._thread(work)

    def _refresh_configs(self) -> None:
        if not hasattr(self, "config_list"):
            return
        path = self.zapret_dir_var.get().strip() if hasattr(self, "zapret_dir_var") else str(self.store.get("zapret_dir", ""))
        self.store.set("zapret_dir", path)
        self.config_list.delete(0, "end")
        configs = self.zapret.discover_configs(path) if path else []
        for config in configs:
            self.config_list.insert("end", config.name)
        selected_name = self.store.get("selected_zapret_config") or self.store.get("best_zapret_config")
        for index, config in enumerate(configs):
            if config.name == selected_name:
                self.config_list.selection_set(index)
                self.config_list.see(index)
                break
        if configs:
            self._log(f"Найдено стратегий: {len(configs)}", self.zapret_log)
        else:
            self._log("Стратегии не найдены. Выберите папку zapret или нажмите 'Скачать latest'.", self.zapret_log)

    def _selected_zapret_config(self) -> Path | None:
        path = self.zapret_dir_var.get().strip() if hasattr(self, "zapret_dir_var") else str(self.store.get("zapret_dir", ""))
        configs = self.zapret.discover_configs(path) if path else []
        selected = self.config_list.curselection() if hasattr(self, "config_list") else []
        if selected and configs:
            return configs[selected[0]]
        best = self.store.get("best_zapret_config")
        for config in configs:
            if config.name == best:
                return config
        return configs[0] if configs else None

    def _use_selected_zapret_config(self) -> None:
        config = self._selected_zapret_config()
        if not config:
            messagebox.showwarning("YouTube и Discord", "Сначала выберите папку zapret.")
            return
        self.store.set("selected_zapret_config", config.name)
        self._log(f"Выбрано: {config.name}", getattr(self, "zapret_log", None))
        if self._is_zapret_running():
            self._start_selected_zapret()
        self._refresh_main_status()

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
            self._refresh_main_status()
        except Exception as exc:
            self._log(f"Ошибка запуска: {exc}", self.zapret_log)

    def _start_best_zapret(self) -> None:
        self._start_selected_zapret()

    def _stop_zapret(self) -> None:
        result = self.zapret.stop_winws()
        message = result.text if result.ok else "Не получилось выключить YouTube и Discord. Попробуйте запустить приложение от администратора."
        if hasattr(self, "zapret_log"):
            self._log(message, self.zapret_log)
        self._log(message)
        self._refresh_main_status()

    def _test_zapret_configs(self, on_done: Callable[[], None] | None = None) -> None:
        path = self.zapret_dir_var.get().strip() if hasattr(self, "zapret_dir_var") else str(self.store.get("zapret_dir", ""))
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
                self.after(0, lambda: self.dashboard_status.configure(text=self._friendly_status_text()))
            self.after(0, self._refresh_configs)
            self.after(0, self._refresh_main_status)
            if on_done:
                self.after(0, on_done)

        self._thread(work)

    def _render_profiles(self) -> None:
        if not hasattr(self, "profile_list"):
            return
        self.profile_list.delete(0, "end")
        selected_id = self.store.get("selected_vpn_profile")
        for index, profile in enumerate(self.store.get("vpn_profiles", [])):
            self.profile_list.insert("end", f"{profile.get('name')} [{profile.get('protocol')}]")
            if profile.get("id") == selected_id:
                self.profile_list.selection_set(index)
                self.profile_list.see(index)

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
        self._log(f"Добавлен VPN профиль: {profile['name']}", getattr(self, "vpn_status", None))
        self._refresh_main_status()

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

    def _use_selected_vpn_profile(self) -> None:
        profile = self._selected_profile()
        if not profile:
            messagebox.showwarning("VPN", "Сначала добавьте VPN.")
            return
        self.store.set("selected_vpn_profile", profile.get("id", ""))
        self._render_profiles()
        self._log(f"Выбрано: {profile.get('name')}", getattr(self, "vpn_status", None))
        self._refresh_main_status()

    def _connect_vpn(self) -> None:
        profile = self._selected_profile()
        if not profile:
            self._open_vpn_setup()
            return
        if not self._profile_tool_available(profile):
            self._open_vpn_setup()
            return
        if self._is_tunnel_running():
            self.singbox.stop()
        self.store.set("selected_vpn_profile", profile.get("id", ""))

        def work() -> None:
            result = self.vpn.connect(profile)
            if result.ok:
                self.store.set("vpn_active_profile", str(profile.get("id", "")))
            self._ui_log(result.message, getattr(self, "vpn_status", None))
            self._ui_log(result.message)
            self.after(0, self._refresh_main_status)

        self._thread(work)

    def _disconnect_vpn(self) -> None:
        profile = self._selected_profile()
        if not profile:
            return

        def work() -> None:
            result = self.vpn.disconnect(profile)
            self.store.set("vpn_active_profile", "")
            self._ui_log(result.message, getattr(self, "vpn_status", None))
            self._ui_log(result.message)
            self.after(0, self._refresh_main_status)

        self._thread(work)

    def _remove_vpn_profile(self) -> None:
        selected = self.profile_list.curselection() if hasattr(self, "profile_list") else []
        if not selected:
            return
        profiles = list(self.store.get("vpn_profiles", []))
        removed = profiles.pop(selected[0])
        self.store.update({"vpn_profiles": profiles, "selected_vpn_profile": ""})
        self._render_profiles()
        if self.store.get("vpn_active_profile") == removed.get("id"):
            self.store.set("vpn_active_profile", "")
        self._log(f"Удалён профиль: {removed.get('name')}", getattr(self, "vpn_status", None))
        self._refresh_main_status()

    def _refresh_vpn_status(self) -> None:
        if not hasattr(self, "vpn_status"):
            return
        self.vpn_status.configure(state="normal")
        tools = self.vpn.detect_tools()
        ready = [name for name, path in tools.items() if path]
        text = "Найдено: " + (", ".join(ready) if ready else "пока ничего")
        self._log(text, self.vpn_status)

    def _install_vpn_component(self, component: str) -> None:
        def work() -> None:
            result = self.vpn.download_and_run_installer(component, lambda msg: self._ui_log(msg, getattr(self, "vpn_status", None)))
            self._ui_log(result.message, getattr(self, "vpn_status", None))
            self._ui_log(result.message)
            self.after(0, self._refresh_main_status)

        self._thread(work)

    def _selected_rule_profile(self) -> dict[str, object] | None:
        selected = self._selected_profile_from_store()
        if selected and str(selected.get("protocol", "")).lower() == "wireguard":
            return selected
        for profile in self.store.get("vpn_profiles", []):
            if str(profile.get("protocol", "")).lower() == "wireguard":
                return profile
        return None

    def _rule_summary_text(self) -> str:
        domains = self.store.get("bypass_domains", [])
        cidrs = self.store.get("bypass_cidrs", [])
        apps = self.store.get("bypass_apps", [])
        return "\n".join(
            [
                "Напрямую (без VPN):",
                "- .ru, .рф, .su и домены из белого списка",
                "- YouTube и Discord остаются в режиме zapret",
                f"- сетей (CIDR): {len(cidrs)}",
                f"- приложений: {len(apps)}",
                "",
                "Через VPN:",
                "- всё остальное, что не попало в правила выше",
                "",
                "Домены из списка:",
                *(f"- {domain}" for domain in domains[:80]),
                *([f"... ещё {len(domains) - 80}"] if len(domains) > 80 else []),
            ]
        )

    def _is_first_run(self) -> bool:
        return not bool(self.store.get("onboarding_done", False)) or int(self.store.get("onboarding_version", 0)) < 2

    def _maybe_show_onboarding(self) -> None:
        if self._is_first_run():
            self._open_onboarding(force=True)

    def _open_onboarding(self, force: bool = False) -> None:
        if not force and not self._is_first_run():
            return
        existing = getattr(self, "onboarding_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return

        steps = [
            {
                "title": "Добро пожаловать",
                "body": "На главном экране всего три переключателя. Если что-то не настроено, CheburNet сам откроет нужную подсказку.",
                "action": ("Открыть главный экран", "dashboard"),
            },
            {
                "title": "YouTube и Discord",
                "body": "Включите первый переключатель. Если zapret ещё не выбран, появятся две кнопки: указать папку или скачать последнюю версию.",
                "action": ("Настроить YouTube и Discord", "zapret_setup"),
            },
            {
                "title": "VPN",
                "body": "Включите VPN, когда нужен весь интернет через выбранный профиль. Если клиента или конфига нет, приложение попросит добавить.",
                "action": ("Настроить VPN", "vpn_setup"),
            },
            {
                "title": "Тунелирование",
                "body": "Этот режим делает так: российские сайты идут напрямую, остальные через VPN. Обычный VPN и тунелирование включаются по очереди.",
                "action": ("Настроить тунелирование", "tunnel_setup"),
            },
        ]

        win = tk.Toplevel(self)
        self.onboarding_window = win
        win.title("Первый запуск")
        win.transient(self)
        win.grab_set()
        win.resizable(False, False)
        win.configure(bg=self.colors["surface"])
        win.geometry("720x420")

        header = tk.Label(
            win,
            text="Быстрый старт",
            bg=self.colors["surface"],
            fg=self.colors["text"],
            font=("Segoe UI Semibold", 20),
        )
        header.pack(anchor="w", padx=22, pady=(18, 6))

        step_var = tk.StringVar()
        title_var = tk.StringVar()
        body_var = tk.StringVar()

        tk.Label(
            win,
            textvariable=step_var,
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=22, pady=(0, 6))

        tk.Label(
            win,
            textvariable=title_var,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            font=("Segoe UI Semibold", 14),
        ).pack(anchor="w", padx=22, pady=(0, 10))

        tk.Label(
            win,
            textvariable=body_var,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            justify="left",
            wraplength=670,
            font=("Segoe UI", 11),
        ).pack(anchor="w", fill="x", padx=22)

        actions = tk.Frame(win, bg=self.colors["surface"])
        actions.pack(fill="x", padx=22, pady=(18, 10))
        action_btn = self._button(actions, "Открыть раздел", lambda: None)
        action_btn.pack(side="left")

        controls = tk.Frame(win, bg=self.colors["surface"])
        controls.pack(fill="x", padx=22, pady=(8, 18))
        back_btn = self._button(controls, "Назад", lambda: None, flat=True)
        back_btn.pack(side="left")
        next_btn = self._button(controls, "Далее", lambda: None)
        next_btn.pack(side="left", padx=(8, 0))
        skip_btn = self._button(controls, "Пропустить", lambda: None, flat=True)
        skip_btn.pack(side="right")

        state = {"index": 0}

        def close_and_mark_done() -> None:
            self.store.update({"onboarding_done": True, "onboarding_version": 2})
            if win.winfo_exists():
                win.destroy()

        def open_action_tab() -> None:
            _, tab = steps[state["index"]]["action"]
            if tab == "zapret_setup":
                self._open_zapret_setup(parent=win)
            elif tab == "vpn_setup":
                self._open_vpn_setup(parent=win)
            elif tab == "tunnel_setup":
                self._open_tunnel_setup(parent=win)
            else:
                self._show_tab(tab)

        def go_prev() -> None:
            state["index"] = max(0, state["index"] - 1)
            render()

        def go_next() -> None:
            state["index"] = min(len(steps) - 1, state["index"] + 1)
            render()

        def render() -> None:
            index = state["index"]
            item = steps[index]
            step_var.set(f"Шаг {index + 1} из {len(steps)}")
            title_var.set(item["title"])
            body_var.set(item["body"])
            label, _tab = item["action"]
            action_btn.configure(text=label, command=open_action_tab)
            back_btn.configure(state="normal" if index > 0 else "disabled")
            if index == len(steps) - 1:
                next_btn.configure(text="Завершить", command=close_and_mark_done)
            else:
                next_btn.configure(text="Далее", command=go_next)

        back_btn.configure(command=go_prev)
        skip_btn.configure(command=close_and_mark_done)
        win.protocol("WM_DELETE_WINDOW", close_and_mark_done)
        render()

    def _sync_whitelist_widgets(self) -> None:
        if hasattr(self, "domains_text") and hasattr(self, "cidrs_text") and hasattr(self, "apps_text"):
            self._save_whitelist()
        else:
            self._load_direct_sites_file()

    def _download_singbox(self) -> None:
        def work() -> None:
            try:
                path = self.singbox.download_latest(lambda msg: self._ui_log(msg, getattr(self, "rules_log", None)))
            except Exception as exc:
                self._ui_log(f"Ошибка скачивания sing-box: {exc}", getattr(self, "rules_log", None))
                return
            self.store.set("singbox_path", str(path))
            self._ui_log("Тунелирование готово к запуску.", getattr(self, "rules_log", None))
            self.after(0, self._refresh_main_status)

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
            self._log(f"Ошибка настройки туннеля: {exc}", getattr(self, "rules_log", None))
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
            self._open_tunnel_setup()
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
            self._ui_log(text, getattr(self, "rules_log", None))

        self._thread(work)

    def _start_rule_tunnel(self) -> None:
        binary = self.singbox.detect_binary(str(self.store.get("singbox_path", "")))
        if not binary:
            self._open_tunnel_setup()
            return
        profile = self._selected_rule_profile()
        if not profile:
            self._open_tunnel_setup()
            return
        generated = self._build_rule_config(show_warnings=True)
        if not generated:
            return
        config_path = str(generated)

        def work() -> None:
            check = self.singbox.check_config(binary, config_path)
            if not check.ok:
                self._ui_log(check.text or "Туннель не прошёл проверку.", getattr(self, "rules_log", None))
                return
            if str(profile.get("protocol", "")).lower() == "wireguard":
                stopped = self.vpn.disconnect(profile)
                if stopped.ok:
                    self.store.set("vpn_active_profile", "")
                    self._ui_log("Обычный VPN выключен перед тунелированием.", getattr(self, "rules_log", None))
            result = self.singbox.start(binary, config_path)
            self._ui_log(result.message, getattr(self, "rules_log", None))
            self._ui_log(result.message)
            self.after(0, self._refresh_main_status)

        self._thread(work)

    def _stop_rule_tunnel(self) -> None:
        def work() -> None:
            result = self.singbox.stop()
            self._ui_log(result.message, getattr(self, "rules_log", None))
            self._ui_log(result.message)
            self.after(0, self._refresh_main_status)

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
                self.store.set("vpn_active_profile", "")
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
