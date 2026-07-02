from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from cheburnet.app.app_state import AppState
from cheburnet.app.core.config import SettingsStore
from cheburnet.app.core.logger import AppLogger
from cheburnet.app.core.system import is_admin
from cheburnet.app.errors import AdminRequiredError, CheburNetError
from cheburnet.app.models.health import HealthCheckResult, HealthStatus
from cheburnet.app.models.vpn_status import VpnStatus
from cheburnet.app.models.zapret_status import ZapretStatus
from cheburnet.app.services.healthcheck_service import HealthcheckService
from cheburnet.app.services.zapret_service import ZapretService

Progress = Callable[[str], None]

ZAPRET_TEST_TARGETS = {
    "youtube": [
        "https://www.youtube.com",
        "https://youtu.be",
        "https://i.ytimg.com",
        "https://redirector.googlevideo.com",
    ],
    "discord": [
        "https://discord.com",
        "https://gateway.discord.gg",
        "https://cdn.discordapp.com",
        "https://updates.discord.com",
    ],
}


class ZapretController:
    def __init__(
        self,
        state: AppState,
        settings: SettingsStore,
        logger: AppLogger,
        service: ZapretService,
        healthcheck: HealthcheckService | None = None,
    ) -> None:
        self.state = state
        self.settings = settings
        self.logger = logger
        self.service = service
        self.healthcheck = healthcheck or HealthcheckService()
        self.test_cancel_requested = False

    def refresh_status(self, check_process: bool = True) -> ZapretStatus:
        if not self.service.is_installed():
            status = ZapretStatus.NOT_INSTALLED
        elif check_process and self.service.is_running():
            status = ZapretStatus.RUNNING
        else:
            status = ZapretStatus.STOPPED
        self.state.set_zapret_status(status)
        return status

    def scripts(self) -> list[Path]:
        return self.service.available_scripts()

    def options(self) -> dict[str, object]:
        return self.service.options()

    def save_options(self, values: dict[str, object]) -> None:
        self.service.set_options(values)
        self.logger.info("Настройки Zapret сохранены")

    def cancel_test(self) -> None:
        self.test_cancel_requested = True
        try:
            self.service.stop()
        except Exception as exc:
            self.logger.warning(f"Остановка текущего Zapret теста: {exc}")
        self.logger.info("Остановка теста Zapret запрошена")

    def set_selected_script(self, value: str | Path) -> Path | None:
        text = str(value).strip()
        if not text:
            self.settings.update({"zapret": {"selected_script": None}})
            return None
        scripts = self.scripts()
        selected = Path(text)
        if not selected.exists():
            selected = next((script for script in scripts if script.name == text), selected)
        if selected.exists():
            self.settings.update({"zapret": {"selected_script": str(selected), "mode": "manual"}})
            self.logger.info(f"Zapret конфиг по умолчанию: {selected.name}")
            return selected
        return None

    def set_install_dir(self, path: str | Path) -> Path:
        root = self.service.set_install_dir(path)
        self.settings.update({"zapret": {"install_dir": str(root), "selected_script": None}})
        self.state.set_zapret_status(ZapretStatus.STOPPED)
        self.logger.info(f"Папка Zapret выбрана: {root}")
        return root

    def download_or_update(self, progress: Progress | None = None) -> Path:
        previous_selected = str(self.settings.section("zapret").get("selected_script") or "")
        root = self.service.download_latest(progress=progress)
        selected_name = Path(previous_selected).name if previous_selected else ""
        next_selected = None
        if selected_name:
            next_selected = next((script for script in self.service.available_scripts(root) if script.name == selected_name), None)
        self.settings.update({"zapret": {"install_dir": str(root), "selected_script": str(next_selected) if next_selected else None}})
        self.state.set_zapret_status(ZapretStatus.STOPPED)
        self.logger.info(f"Zapret установлен: {root}")
        return root

    def update_ipset_list(self) -> str:
        path = self.service.update_ipset_list()
        message = f"IPSet обновлён: {path}"
        self.logger.info(message)
        return message

    def update_hosts_file(self) -> str:
        if not is_admin():
            raise AdminRequiredError("Для обновления hosts нужны права администратора.")
        message = self.service.update_hosts_file()
        self.logger.info(message)
        return message

    def check_for_updates(self) -> str:
        message = self.service.check_for_updates()
        self.logger.info(message)
        return message

    def run_diagnostics(self) -> str:
        message = self.service.run_diagnostics()
        self.logger.info("Диагностика Zapret выполнена")
        return message

    def start(self, script: Path | None = None) -> None:
        if not is_admin():
            raise AdminRequiredError("Для Zapret нужны права администратора.")
        scripts = self.scripts()
        selected = script or self._selected_script(scripts)
        if not selected:
            raise CheburNetError("Сценарии Zapret не найдены. Скачайте модуль или выберите папку.")
        self.state.set_zapret_status(ZapretStatus.STARTING)
        mode = str(self.settings.section("zapret").get("mode", "auto"))
        if mode == "auto" and script is None:
            self._start_auto(scripts)
            return
        self.logger.info(f"Запускаю Zapret: {selected.name}")
        try:
            self.service.start_script(selected, on_output=self.logger.info)
            if not self.service.is_running():
                raise CheburNetError("Zapret запустился, но рабочий процесс не найден.")
            self.settings.update({"zapret": {"enabled": True, "selected_script": str(selected)}})
            self.state.set_zapret_status(ZapretStatus.RUNNING)
            self._update_routes_running()
            self.check_services()
            self.logger.info("Zapret включен")
        except Exception as exc:
            self.state.set_zapret_status(ZapretStatus.ERROR, str(exc))
            self.logger.error(f"Ошибка Zapret: {exc}")
            raise

    def stop(self) -> None:
        self.state.set_zapret_status(ZapretStatus.STOPPING)
        self.service.stop()
        self.settings.update({"zapret": {"enabled": False}})
        self.state.set_zapret_status(ZapretStatus.STOPPED)
        self.state.set_health("youtube", HealthCheckResult("youtube", HealthStatus.UNCHECKED))
        self.state.set_health("discord", HealthCheckResult("discord", HealthStatus.UNCHECKED))
        if self.state.vpn_status == VpnStatus.CONNECTED:
            self.state.set_routes({"youtube": "VPN", "discord": "VPN", "other": "VPN"})
        else:
            self.state.set_routes({"youtube": "direct", "discord": "direct", "other": "direct"})
        self.logger.info("Zapret выключен")

    def toggle(self) -> None:
        if self.state.zapret_status == ZapretStatus.RUNNING or self.service.is_running():
            self.stop()
        else:
            self.start()

    def _selected_script(self, scripts: list[Path]) -> Path | None:
        configured = self.settings.section("zapret").get("selected_script")
        if configured:
            path = Path(str(configured))
            if path.exists():
                return path
            for script in scripts:
                if script.name == configured:
                    return script
        return scripts[0] if scripts else None

    def check_services(self) -> dict[str, HealthCheckResult]:
        self.state.set_health("youtube", HealthCheckResult("youtube", HealthStatus.CHECKING))
        self.state.set_health("discord", HealthCheckResult("discord", HealthStatus.CHECKING))
        results = self.healthcheck.check_youtube_discord()
        for service, result in results.items():
            self.state.set_health(service, result)
            self.logger.info(f"{service}: {result.status.value} {result.detail}")
        return results

    def test_all_scripts(self, progress: Progress | None = None) -> list[dict[str, object]]:
        if not is_admin():
            raise AdminRequiredError("Для теста Zapret нужны права администратора.")
        scripts = self.scripts()
        if not scripts:
            raise CheburNetError("Сценарии Zapret не найдены.")
        self.test_cancel_requested = False
        results: list[dict[str, object]] = []
        best: dict[str, object] | None = None
        canceled = False
        zapret_settings = self.settings.section("zapret")
        configured = str(zapret_settings.get("selected_script") or "")
        had_manual_selection = bool(configured) and str(zapret_settings.get("mode", "auto")) == "manual"
        was_running = self.state.zapret_status == ZapretStatus.RUNNING or self.service.is_running()
        restore_script = self._selected_script(scripts)
        self.state.set_zapret_status(ZapretStatus.STARTING)
        try:
            for index, script in enumerate(scripts, start=1):
                if self.test_cancel_requested:
                    canceled = True
                    break
                if progress:
                    progress(f"Тест Zapret {index}/{len(scripts)}: {script.name}")
                try:
                    self.service.stop()
                except Exception:
                    pass
                error = ""
                group_results: dict[str, list[HealthCheckResult]] = {"youtube": [], "discord": []}
                try:
                    self.service.start_script(script)
                    if self._sleep_or_cancel(3):
                        canceled = True
                        if progress:
                            progress("Тест Zapret остановлен")
                        break
                    if not self.service.is_running():
                        raise CheburNetError("рабочий процесс winws не найден")
                    group_results = self._check_zapret_test_targets()
                    if self.test_cancel_requested:
                        canceled = True
                        if progress:
                            progress("Тест Zapret остановлен")
                        break
                except Exception as exc:
                    error = str(exc)
                    self.logger.warning(f"Zapret тест {script.name}: {error}")
                finally:
                    try:
                        self.service.stop()
                    except Exception:
                        pass
                if canceled:
                    break
                youtube_ok = sum(1 for item in group_results["youtube"] if item.status == HealthStatus.OK)
                discord_ok = sum(1 for item in group_results["discord"] if item.status == HealthStatus.OK)
                score = youtube_ok + discord_ok
                detail = error or self._zapret_test_detail(group_results)
                row = {
                    "script": script.name,
                    "path": str(script),
                    "youtube": f"{youtube_ok}/{len(ZAPRET_TEST_TARGETS['youtube'])}",
                    "discord": f"{discord_ok}/{len(ZAPRET_TEST_TARGETS['discord'])}",
                    "detail": detail,
                    "score": score,
                    "total": len(ZAPRET_TEST_TARGETS["youtube"]) + len(ZAPRET_TEST_TARGETS["discord"]),
                }
                results.append(row)
                if progress:
                    progress("zapret_test_row:" + json.dumps(row, ensure_ascii=False))
                if best is None or score > int(best.get("score", 0)):
                    best = row
            if best and int(best.get("score", 0)) > 0 and not had_manual_selection and not canceled:
                self.settings.update({"zapret": {"selected_script": str(best["path"]), "mode": "manual"}})
                restore_script = Path(str(best["path"]))
                self.logger.info(f"Zapret тест: выбран {best['script']}")
            if canceled:
                self.logger.info("Тест Zapret остановлен пользователем")
        finally:
            if was_running and restore_script:
                try:
                    self.service.start_script(restore_script, on_output=self.logger.info)
                    self.settings.update({"zapret": {"enabled": True, "selected_script": str(restore_script)}})
                    self.state.set_zapret_status(ZapretStatus.RUNNING)
                    self._update_routes_running()
                except Exception as exc:
                    self.state.set_zapret_status(ZapretStatus.ERROR, str(exc))
                    self.logger.error(f"Zapret не удалось восстановить после теста: {exc}")
            else:
                self.settings.update({"zapret": {"enabled": False}})
                self.state.set_zapret_status(ZapretStatus.STOPPED)
        return results

    def _sleep_or_cancel(self, seconds: float) -> bool:
        deadline = time.time() + seconds
        while time.time() < deadline:
            if self.test_cancel_requested:
                return True
            time.sleep(0.1)
        return self.test_cancel_requested

    def _check_zapret_test_targets(self) -> dict[str, list[HealthCheckResult]]:
        jobs: dict[object, tuple[str, str]] = {}
        results: dict[str, list[HealthCheckResult]] = {"youtube": [], "discord": []}
        executor = ThreadPoolExecutor(max_workers=4)
        try:
            for group, urls in ZAPRET_TEST_TARGETS.items():
                for url in urls:
                    future = executor.submit(self.healthcheck.http_check, url, 4.0)
                    jobs[future] = (group, url)
            for future in as_completed(jobs):
                if self.test_cancel_requested:
                    break
                group, url = jobs[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = HealthCheckResult(url, HealthStatus.FAILED, str(exc))
                results[group].append(result)
        finally:
            if self.test_cancel_requested:
                for future in jobs:
                    future.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
            else:
                executor.shutdown(wait=True)
        return results

    @staticmethod
    def _zapret_test_detail(results: dict[str, list[HealthCheckResult]]) -> str:
        failed: list[str] = []
        for group, checks in results.items():
            for item in checks:
                if item.status != HealthStatus.OK:
                    failed.append(f"{group}: {ZapretController._simple_detail(item)}")
        return "; ".join(dict.fromkeys(failed[:6])) or "Все тестовые цели доступны"

    @staticmethod
    def _simple_detail(item: HealthCheckResult) -> str:
        text = (item.detail or item.status.value or "").lower()
        if item.status == HealthStatus.TIMEOUT or "timeout" in text or "таймаут" in text:
            return "таймаут"
        if "getaddrinfo" in text or "11001" in text or "name or service" in text:
            return "DNS не ответил"
        if "forbidden" in text or " 403" in text:
            return "доступ запрещён"
        if "not found" in text or " 404" in text:
            return "страница не найдена"
        if item.status == HealthStatus.FAILED:
            return "нет ответа"
        return item.detail or item.status.value

    def _start_auto(self, scripts: list[Path]) -> None:
        last_error = ""
        for script in scripts:
            self.logger.info(f"Auto Zapret: пробую {script.name}")
            try:
                self.service.stop()
            except Exception:
                pass
            try:
                self.service.start_script(script, on_output=self.logger.info)
                time.sleep(3)
                if not self.service.is_running():
                    raise CheburNetError("рабочий процесс winws не найден")
                results = self.check_services()
                if all(result.status == HealthStatus.OK for result in results.values()):
                    self.settings.update({"zapret": {"enabled": True, "selected_script": str(script)}})
                    self.state.set_zapret_status(ZapretStatus.RUNNING)
                    self._update_routes_running()
                    self.logger.info(f"Auto Zapret: выбран {script.name}")
                    return
                last_error = "; ".join(f"{name}: {result.detail}" for name, result in results.items())
            except Exception as exc:
                last_error = str(exc)
                self.logger.warning(f"Auto Zapret: {script.name} не подошёл: {exc}")
            try:
                self.service.stop()
            except Exception:
                pass
        self.state.set_zapret_status(ZapretStatus.ERROR, last_error)
        raise CheburNetError(f"Auto Zapret не нашёл рабочий сценарий. {last_error}")

    def _update_routes_running(self) -> None:
        if self.state.vpn_status == VpnStatus.CONNECTED:
            self.state.set_routes({"youtube": "direct + Zapret", "discord": "direct + Zapret", "other": "VPN"})
        else:
            self.state.set_routes({"youtube": "direct + Zapret", "discord": "direct + Zapret", "other": "direct"})
