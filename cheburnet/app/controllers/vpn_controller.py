from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from cheburnet.app.app_state import AppState
from cheburnet.app.core.config import SettingsStore
from cheburnet.app.core.logger import AppLogger
from cheburnet.app.core.system import is_admin
from cheburnet.app.errors import AdminRequiredError, CheburNetError
from cheburnet.app.models.profile import Profile, RoutingMode
from cheburnet.app.models.vpn_status import VpnStatus
from cheburnet.app.models.zapret_status import ZapretStatus
from cheburnet.app.services.free_configs_service import FreeConfigsService
from cheburnet.app.services.healthcheck_service import HealthcheckService
from cheburnet.app.services.profile_store import ProfileStore
from cheburnet.app.services.singbox_config_builder import SingBoxConfigBuilder
from cheburnet.app.services.singbox_service import SingBoxService
from cheburnet.app.services.wireguard_importer import WireGuardImporter

Progress = Callable[[str], None]


class VpnController:
    def __init__(
        self,
        state: AppState,
        settings: SettingsStore,
        profiles: ProfileStore,
        logger: AppLogger,
        singbox: SingBoxService,
        builder: SingBoxConfigBuilder,
        free_configs: FreeConfigsService,
        wireguard: WireGuardImporter,
        healthcheck: HealthcheckService,
    ) -> None:
        self.state = state
        self.settings = settings
        self.profiles = profiles
        self.logger = logger
        self.singbox = singbox
        self.builder = builder
        self.free_configs = free_configs
        self.wireguard = wireguard
        self.healthcheck = healthcheck
        self.cancel_requested = False

    def load_profiles(self) -> list[Profile]:
        items = self.profiles.load()
        self.state.set_servers(items)
        selected = self.profiles.get(self.settings.get("selected_profile_id"))
        self.state.set_selected_profile(selected or (items[0] if items else None))
        return items

    def select_profile(self, profile_id: str) -> Profile | None:
        profile = self.profiles.get(profile_id)
        if profile:
            self.settings.set("selected_profile_id", profile.id)
            self.state.set_selected_profile(profile)
            self.logger.info(f"Профиль выбран: {profile.name}")
        return profile

    def import_wireguard(self, path: str | Path) -> Profile:
        profile = self.wireguard.import_file(path)
        self.profiles.upsert(profile)
        self.select_profile(profile.id)
        self.state.set_servers(self.profiles.all())
        self.logger.info(f"Добавлен WireGuard профиль: {profile.name}")
        return profile

    def add_uri(self, uri: str) -> Profile:
        profile = self.free_configs.parse_link(uri, "manual")
        if not profile:
            raise CheburNetError("Не удалось разобрать ссылку профиля.")
        profile.source = "manual"
        self.profiles.upsert(profile)
        self.select_profile(profile.id)
        self.state.set_servers(self.profiles.all())
        self.logger.info(f"Добавлен профиль: {profile.name}")
        return profile

    def import_profile_list_text(self, text: str, source: str = "file") -> list[Profile]:
        profiles = self.free_configs.parse_text(text, source)
        if not profiles:
            raise CheburNetError("В списке не найдены поддерживаемые профили.")
        for profile in profiles:
            profile.source = source
            profile.status = "unchecked"
        self.profiles.upsert_many(profiles)
        items = self.profiles.all()
        self.state.set_servers(items)
        if not self.state.selected_profile:
            self.select_profile(profiles[0].id)
        self.logger.info(f"Импортировано профилей: {len(profiles)}")
        return profiles

    def add_subscription_source(self, url: str) -> str:
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CheburNetError("Подписка должна быть http/https ссылкой.")
        section = self.settings.section("free_configs")
        sources = [str(item).strip() for item in section.get("sources", []) if str(item).strip()]
        if url not in sources:
            sources.append(url)
        self.settings.update({"free_configs": {"sources": sources}})
        self.logger.info(f"Добавлена подписка: {url}")
        return url

    def update_free_configs(self, progress: Progress | None = None) -> list[Profile]:
        section = self.settings.section("free_configs")
        sources = [str(item).strip() for item in section.get("sources", []) if str(item).strip()]
        if not sources:
            raise CheburNetError("Добавьте URL списка профилей перед обновлением.")
        if progress:
            progress("Загружаю профили из пользовательских списков")
        profiles = self.free_configs.fetch(sources=sources)
        for profile in profiles:
            profile.source = "user-list"
            profile.status = "unchecked"
        self.profiles.upsert_many(profiles)
        self.state.set_servers(self.profiles.all())
        self.logger.info(f"Профили из пользовательских списков загружены: {len(profiles)}")
        if profiles:
            binary = self.singbox.ensure_installed(progress=progress)
            version = self.singbox.version(binary)
            for index, profile in enumerate(profiles, start=1):
                if progress:
                    progress(f"Проверяю профиль {index}/{len(profiles)}: {profile.name}")
                self.check_profile(profile, binary=binary, version=version, progress=progress)
            self._sort_profiles()
        return profiles

    def check_profile(
        self,
        profile: Profile,
        binary: Path | None = None,
        version: str | None = None,
        progress: Progress | None = None,
    ) -> Profile:
        if binary is None:
            binary = self.singbox.ensure_installed(progress=progress)
        if version is None:
            version = self.singbox.version(binary)
        profile = self.healthcheck.check_profile_with_singbox(profile, binary, self.builder, self.settings.data, version, progress)
        self.profiles.upsert(profile)
        self._sort_profiles()
        self.logger.info(f"Проверка {profile.name}: {profile.status} {profile.latency_ms or '-'} ms")
        return profile

    def connect_selected_profile(self, progress: Progress | None = None) -> None:
        self.cancel_requested = False
        if not is_admin():
            raise AdminRequiredError("Для VPN/TUN нужны права администратора.")
        profile = self.state.selected_profile or self.profiles.get(self.settings.get("selected_profile_id"))
        if not profile:
            raise CheburNetError("Выберите VPN профиль перед подключением.")
        mode = self._effective_routing_mode()
        if mode == RoutingMode.ZAPRET_ONLY:
            raise CheburNetError("В режиме Zapret only VPN не запускается.")

        self.state.set_vpn_status(VpnStatus.CONNECTING)
        self.logger.info("Подключаю VPN")
        try:
            binary = self.singbox.ensure_installed(progress=progress)
            version = self.singbox.version(binary)
            if progress:
                progress(f"sing-box: {version or binary}")
            auto_failover = bool(self.settings.section("vpn").get("auto_failover", False))
            candidates = self._connection_candidates(profile) if auto_failover else [profile]
            last_error = ""
            for index, candidate in enumerate(candidates, start=1):
                if auto_failover and progress:
                    progress(f"VPN профиль {index}/{len(candidates)}: {candidate.name}")
                try:
                    self._connect_profile(candidate, mode, binary, version)
                    return
                except Exception as exc:
                    last_error = str(exc)
                    try:
                        self.singbox.stop()
                    except Exception:
                        pass
                    candidate.status = "failed"
                    candidate.meta["last_connect_error"] = last_error
                    self.profiles.upsert(candidate)
                    self._sort_profiles()
                    if not auto_failover or index == len(candidates):
                        raise
                    self.logger.warning(f"VPN профиль не подошел, пробую следующий: {candidate.name}: {last_error}")
            if last_error:
                raise CheburNetError(last_error)
        except Exception as exc:
            if self.cancel_requested:
                try:
                    self.singbox.stop()
                except Exception:
                    pass
                self.state.set_vpn_status(VpnStatus.DISCONNECTED)
                self.logger.info("Запуск VPN отменен")
                return
            self.state.set_vpn_status(VpnStatus.ERROR, str(exc))
            self.logger.error(f"Ошибка VPN: {exc}")
            raise

    def _connect_profile(self, profile: Profile, mode: RoutingMode, binary: Path, version: str) -> None:
        if profile.protocol != "wireguard":
            endpoint = self.healthcheck.tcp_check(profile)
            if endpoint.status != "online":
                raise CheburNetError(f"Endpoint недоступен: {endpoint.detail}")
        config_path = self.builder.build(profile, self.settings.data, mode, version)
        self.logger.info("sing-box config.json сгенерирован")
        check = self.singbox.check_config(binary, config_path)
        if not check.ok:
            raise CheburNetError(check.text or "sing-box check завершился с ошибкой.")
        self.logger.info("sing-box check: OK")
        if self.cancel_requested:
            self.state.set_vpn_status(VpnStatus.DISCONNECTED)
            self.logger.info("Запуск VPN отменен")
            return
        self.singbox.start(binary, config_path, on_output=self.logger.info)
        ready = self.healthcheck.check_vpn_ready(profile)
        if self.cancel_requested:
            self.singbox.stop()
            self.state.set_vpn_status(VpnStatus.DISCONNECTED)
            self.logger.info("Запуск VPN отменен")
            return
        if ready.status != "online":
            self.singbox.stop()
            raise CheburNetError(f"VPN health-check не прошёл: {ready.detail}")
        profile.status = "online"
        profile.latency_ms = ready.latency_ms
        self.profiles.upsert(profile)
        self.settings.set("selected_profile_id", profile.id)
        self.state.set_selected_profile(profile)
        self._sort_profiles()
        self._update_routes(mode)
        if self.cancel_requested:
            self.singbox.stop()
            self.state.set_vpn_status(VpnStatus.DISCONNECTED)
            self.logger.info("Запуск VPN отменен")
            return
        self.state.set_vpn_status(VpnStatus.CONNECTED)
        self.logger.info("VPN подключен")

    def _effective_routing_mode(self) -> RoutingMode:
        return RoutingMode(str(self.settings.get("routing_mode", RoutingMode.FULL_VPN.value)))

    def _connection_candidates(self, selected: Profile) -> list[Profile]:
        priority = {"online": 0, "unstable": 1, "unchecked": 2, "failed": 3, "syntax_error": 4, "tcp_failed": 5}
        candidates = [profile for profile in self.profiles.all() if profile.id != selected.id]
        candidates.sort(
            key=lambda profile: (
                priority.get(profile.status, 9),
                profile.latency_ms if profile.latency_ms is not None else 999999,
                profile.name.lower(),
            )
        )
        return [selected, *candidates]

    def disconnect(self) -> None:
        self.cancel_requested = True
        self.state.set_vpn_status(VpnStatus.DISCONNECTING)
        self.singbox.stop()
        self.state.set_vpn_status(VpnStatus.DISCONNECTED)
        if self.state.zapret_status == ZapretStatus.RUNNING:
            self.state.set_routes({"youtube": "direct + Zapret", "discord": "direct + Zapret", "other": "direct"})
        else:
            self.state.set_routes({"youtube": "direct", "discord": "direct", "other": "direct"})
        self.logger.info("VPN отключен")

    def delete_profile(self, profile_id: str) -> None:
        if self.profiles.delete(profile_id):
            self.logger.info("Профиль удалён")
        items = self.profiles.all()
        self.state.set_servers(items)
        if self.state.selected_profile and self.state.selected_profile.id == profile_id:
            selected = items[0] if items else None
            self.state.set_selected_profile(selected)
            self.settings.set("selected_profile_id", selected.id if selected else None)

    def _update_routes(self, mode: RoutingMode) -> None:
        if mode == RoutingMode.SMART_SPLIT:
            route = "direct + Zapret" if self.state.zapret_status == ZapretStatus.RUNNING else "direct"
            self.state.set_routes({"youtube": route, "discord": route, "other": "VPN"})
        elif mode == RoutingMode.CUSTOM_SPLIT:
            self.state.set_routes({"youtube": "по правилам", "discord": "по правилам", "other": "VPN + direct exceptions"})
        else:
            self.state.set_routes({"youtube": "VPN", "discord": "VPN", "other": "VPN + direct exceptions"})

    def _sort_profiles(self) -> None:
        priority = {"online": 0, "unstable": 1, "unchecked": 2, "failed": 3, "syntax_error": 4, "tcp_failed": 5}
        items = sorted(
            self.profiles.all(),
            key=lambda profile: (
                priority.get(profile.status, 9),
                profile.latency_ms if profile.latency_ms is not None else 999999,
                profile.name.lower(),
            ),
        )
        self.profiles.profiles = items
        self.profiles.save()
        self.state.set_servers(items)
        if self.state.selected_profile:
            selected = next((profile for profile in items if profile.id == self.state.selected_profile.id), None)
            self.state.set_selected_profile(selected)
