from __future__ import annotations

from cheburnet.app.app_state import AppState
from cheburnet.app.controllers.vpn_controller import VpnController
from cheburnet.app.controllers.zapret_controller import ZapretController
from cheburnet.app.core.config import SettingsStore
from cheburnet.app.core.logger import AppLogger
from cheburnet.app.core.process import CommandResult
from cheburnet.app.models.health import HealthCheckResult, HealthStatus
from cheburnet.app.models.profile import Profile
from cheburnet.app.models.server import ServerCheck
from cheburnet.app.models.vpn_status import VpnStatus
from cheburnet.app.models.zapret_status import ZapretStatus
from cheburnet.app.services.profile_store import ProfileStore
from cheburnet.app.services.zapret_service import ZapretService


class FakeSingBox:
    def ensure_installed(self, progress=None):
        return "sing-box.exe"

    def version(self, binary):
        return "1.12.0"

    def check_config(self, binary, config_path):
        return CommandResult(True, ["check"], 0, "ok", "")

    def start(self, binary, config_path, on_output=None):
        return None

    def stop(self):
        return None


class FakeBuilder:
    def __init__(self, tmp_path) -> None:
        self.tmp_path = tmp_path

    def build(self, profile, settings, mode, version):
        if profile.id == "bad":
            raise RuntimeError("broken profile")
        config = self.tmp_path / f"{profile.id}.json"
        config.write_text("{}", encoding="utf-8")
        return config


class FakeVpnHealth:
    def tcp_check(self, profile):
        return ServerCheck(profile.id, "online", 3, "TCP OK")

    def check_vpn_ready(self, profile):
        return ServerCheck(profile.id, "online", 5, "HTTP 204")


def test_vpn_auto_failover_selects_next_working_profile(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("cheburnet.app.controllers.vpn_controller.is_admin", lambda: True)
    state = AppState()
    settings = SettingsStore(tmp_path / "settings.json")
    settings.update({"vpn": {"auto_failover": True}, "selected_profile_id": "bad"})
    store = ProfileStore(tmp_path / "profiles.json")
    bad = Profile(id="bad", name="Bad", protocol="vless", host="bad.example", port=443)
    good = Profile(id="good", name="Good", protocol="vless", host="good.example", port=443, status="online", latency_ms=10)
    store.upsert_many([bad, good])
    state.set_servers(store.all())
    state.set_selected_profile(bad)
    controller = VpnController(
        state,
        settings,
        store,
        AppLogger(path=tmp_path / "app.log"),
        FakeSingBox(),
        FakeBuilder(tmp_path),
        object(),
        object(),
        FakeVpnHealth(),
    )

    controller.connect_selected_profile()

    assert state.vpn_status == VpnStatus.CONNECTED
    assert state.selected_profile and state.selected_profile.id == "good"
    assert settings.get("selected_profile_id") == "good"


def test_zapret_service_accepts_user_selected_folder(tmp_path) -> None:
    root = tmp_path / "zapret-discord-youtube"
    root.mkdir()
    (root / "service.bat").write_text("@echo off\n", encoding="utf-8")
    (root / "general.bat").write_text("@echo off\n", encoding="utf-8")

    service = ZapretService()
    selected = service.set_install_dir(root)

    assert selected == root
    assert [script.name for script in service.available_scripts()] == ["general.bat"]


def test_zapret_update_extracts_next_to_existing_root(tmp_path, monkeypatch) -> None:
    old_root = tmp_path / "zapret-discord-youtube-1.9.9b"
    old_root.mkdir()
    (old_root / "service.bat").write_text('@echo off\nset "LOCAL_VERSION=1.9.9b"\n', encoding="utf-8")
    (old_root / "general.bat").write_text("@echo off\n", encoding="utf-8")
    service = ZapretService(old_root)

    monkeypatch.setattr(
        service,
        "latest_release",
        lambda: {
            "tag_name": "1.9.9c",
            "assets": [{"name": "zapret.zip", "browser_download_url": "https://example.com/zapret.zip"}],
        },
    )
    monkeypatch.setattr("cheburnet.app.services.zapret_service.download_file", lambda _url, path, _progress=None: path.write_text("zip", encoding="utf-8"))

    def fake_extract(_archive_path, destination):
        destination.mkdir(parents=True)
        root = destination / "zapret-discord-youtube"
        root.mkdir()
        (root / "service.bat").write_text('@echo off\nset "LOCAL_VERSION=1.9.9c"\n', encoding="utf-8")
        (root / "general.bat").write_text("@echo off\n", encoding="utf-8")
        return destination

    monkeypatch.setattr("cheburnet.app.services.zapret_service.extract_archive", fake_extract)

    new_root = service.download_latest()

    assert new_root == tmp_path / "zapret-discord-youtube-1.9.9c" / "zapret-discord-youtube"
    assert old_root not in new_root.parents
    assert service.install_dir() == new_root


def test_zapret_update_from_nested_root_uses_sibling_version_dir(tmp_path, monkeypatch) -> None:
    base = tmp_path / "zapret"
    old_root = base / "zapret-discord-youtube-1.9.9b" / "zapret-discord-youtube"
    old_root.mkdir(parents=True)
    (old_root / "service.bat").write_text('@echo off\nset "LOCAL_VERSION=1.9.9b"\n', encoding="utf-8")
    (old_root / "general.bat").write_text("@echo off\n", encoding="utf-8")
    service = ZapretService(old_root)

    monkeypatch.setattr(
        service,
        "latest_release",
        lambda: {
            "tag_name": "1.9.9c",
            "assets": [{"name": "zapret.zip", "browser_download_url": "https://example.com/zapret.zip"}],
        },
    )
    monkeypatch.setattr("cheburnet.app.services.zapret_service.download_file", lambda _url, path, _progress=None: path.write_text("zip", encoding="utf-8"))

    def fake_extract(_archive_path, destination):
        destination.mkdir(parents=True)
        root = destination / "zapret-discord-youtube"
        root.mkdir()
        (root / "service.bat").write_text('@echo off\nset "LOCAL_VERSION=1.9.9c"\n', encoding="utf-8")
        (root / "general.bat").write_text("@echo off\n", encoding="utf-8")
        return destination

    monkeypatch.setattr("cheburnet.app.services.zapret_service.extract_archive", fake_extract)

    new_root = service.download_latest()

    assert new_root == base / "zapret-discord-youtube-1.9.9c" / "zapret-discord-youtube"
    assert old_root not in new_root.parents


def test_zapret_update_cleans_old_managed_versions(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CHEBURNET_HOME", str(tmp_path))
    base = tmp_path / "tools" / "zapret"
    old_root = base / "zapret-discord-youtube-1.9.9b" / "zapret-discord-youtube"
    old_root.mkdir(parents=True)
    (old_root / "service.bat").write_text('@echo off\nset "LOCAL_VERSION=1.9.9b"\n', encoding="utf-8")
    (old_root / "general.bat").write_text("@echo off\n", encoding="utf-8")
    service = ZapretService(old_root)

    monkeypatch.setattr(
        service,
        "latest_release",
        lambda: {
            "tag_name": "1.9.9c",
            "assets": [{"name": "zapret.zip", "browser_download_url": "https://example.com/zapret.zip"}],
        },
    )
    monkeypatch.setattr("cheburnet.app.services.zapret_service.download_file", lambda _url, path, _progress=None: path.write_text("zip", encoding="utf-8"))

    def fake_extract(_archive_path, destination):
        root = destination / "zapret-discord-youtube"
        root.mkdir(parents=True)
        (root / "service.bat").write_text('@echo off\nset "LOCAL_VERSION=1.9.9c"\n', encoding="utf-8")
        (root / "general.bat").write_text("@echo off\n", encoding="utf-8")
        return destination

    monkeypatch.setattr("cheburnet.app.services.zapret_service.extract_archive", fake_extract)

    service.download_latest()

    assert not old_root.parent.exists()
    assert (base / "zapret-discord-youtube-1.9.9c").exists()


def test_zapret_hidden_script_replaces_visible_start(tmp_path) -> None:
    script = tmp_path / "general.bat"
    script.write_text('start "zapret: %~n0" /min "%BIN%winws.exe" --flag\n', encoding="utf-8")

    hidden = ZapretService._hidden_script(script)

    text = hidden.read_text(encoding="utf-8")
    assert 'start "" /b "%BIN%winws.exe"' in text
    assert hidden.name.startswith("cheburnet-hidden-")


def test_zapret_builds_hidden_winws_command_from_bat(tmp_path) -> None:
    root = tmp_path / "zapret-discord-youtube"
    (root / "bin").mkdir(parents=True)
    (root / "lists").mkdir()
    (root / "utils").mkdir()
    (root / "utils" / "game_filter.enabled").write_text("udp", encoding="utf-8")
    winws = root / "bin" / "winws.exe"
    winws.write_text("", encoding="utf-8")
    script = root / "general.bat"
    script.write_text(
        'start "zapret: %~n0" /min "%BIN%winws.exe" ^\n'
        "--wf-tcp=80,443 --wf-udp=%GameFilterUDP% --hostlist=\"%LISTS%list-general.txt\"\n",
        encoding="utf-8",
    )

    command, args = ZapretService.build_winws_command(script)

    assert command == winws
    assert "--wf-tcp=80,443" in args
    assert "--wf-udp=50000-65535" in args
    assert any("list-general.txt" in arg for arg in args)


def test_zapret_options_write_real_filter_files(tmp_path) -> None:
    root = tmp_path / "zapret-discord-youtube"
    (root / "utils").mkdir(parents=True)
    (root / "lists").mkdir()
    (root / "general.bat").write_text("@echo off\n", encoding="utf-8")
    (root / "lists" / "ipset-all.txt").write_text("1.1.1.1/32\n", encoding="utf-8")
    service = ZapretService(root)

    service.set_options({"game_filter": "udp", "ipset_filter": False, "update_check": True})

    assert (root / "utils" / "game_filter.enabled").read_text(encoding="utf-8") == "udp"
    assert "203.0.113.113/32" in (root / "lists" / "ipset-all.txt").read_text(encoding="utf-8")
    assert (root / "lists" / "ipset-all.cheburnet-backup.txt").exists()
    assert (root / "utils" / "check_updates.enabled").exists()
    assert service.options() == {"game_filter": "udp", "ipset_filter": False, "update_check": True}

    service.set_options({"game_filter": "off", "ipset_filter": True, "update_check": False})

    assert not (root / "utils" / "game_filter.enabled").exists()
    assert "1.1.1.1/32" in (root / "lists" / "ipset-all.txt").read_text(encoding="utf-8")
    assert not (root / "utils" / "check_updates.enabled").exists()
    assert service.options() == {"game_filter": "off", "ipset_filter": True, "update_check": False}


class FakeZapretService:
    def __init__(self, scripts, best_script) -> None:
        self._scripts = scripts
        self.best_script = best_script
        self.current = None
        self.running = False
        self.started = []

    def available_scripts(self):
        return self._scripts

    def is_running(self):
        return self.running

    def is_installed(self):
        return True

    def start_script(self, script, on_output=None):
        self.current = script
        self.running = True
        self.started.append(script.name)

    def stop(self):
        self.running = False


class FakeZapretHealth:
    def __init__(self, service: FakeZapretService) -> None:
        self.service = service

    def http_check(self, target: str, timeout: float = 8.0):
        status = HealthStatus.OK if self.service.current == self.service.best_script else HealthStatus.FAILED
        return HealthCheckResult(target, status, "ok" if status == HealthStatus.OK else "failed")


def test_zapret_test_all_keeps_manual_selection(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("cheburnet.app.controllers.zapret_controller.is_admin", lambda: True)
    monkeypatch.setattr("cheburnet.app.controllers.zapret_controller.time.sleep", lambda _seconds: None)
    script_a = tmp_path / "general.bat"
    script_b = tmp_path / "general ALT.bat"
    script_a.write_text("@echo off\n", encoding="utf-8")
    script_b.write_text("@echo off\n", encoding="utf-8")
    settings = SettingsStore(tmp_path / "settings.json")
    settings.update({"zapret": {"selected_script": str(script_a), "mode": "manual"}})
    service = FakeZapretService([script_a, script_b], script_b)
    controller = ZapretController(AppState(), settings, AppLogger(path=tmp_path / "app.log"), service, FakeZapretHealth(service))
    controller._sleep_or_cancel = lambda _seconds: False

    rows = controller.test_all_scripts()

    assert len(rows) == 2
    assert settings.section("zapret")["selected_script"] == str(script_a)
    assert settings.section("zapret")["mode"] == "manual"


def test_zapret_test_all_selects_best_when_no_manual_selection(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("cheburnet.app.controllers.zapret_controller.is_admin", lambda: True)
    monkeypatch.setattr("cheburnet.app.controllers.zapret_controller.time.sleep", lambda _seconds: None)
    script_a = tmp_path / "general.bat"
    script_b = tmp_path / "general ALT.bat"
    script_a.write_text("@echo off\n", encoding="utf-8")
    script_b.write_text("@echo off\n", encoding="utf-8")
    settings = SettingsStore(tmp_path / "settings.json")
    service = FakeZapretService([script_a, script_b], script_b)
    controller = ZapretController(AppState(), settings, AppLogger(path=tmp_path / "app.log"), service, FakeZapretHealth(service))
    controller._sleep_or_cancel = lambda _seconds: False

    rows = controller.test_all_scripts()

    assert max(row["score"] for row in rows) == 8
    assert settings.section("zapret")["selected_script"] == str(script_b)
    assert settings.section("zapret")["mode"] == "manual"


def test_zapret_test_all_can_be_cancelled(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("cheburnet.app.controllers.zapret_controller.is_admin", lambda: True)
    monkeypatch.setattr("cheburnet.app.controllers.zapret_controller.time.sleep", lambda _seconds: None)
    script_a = tmp_path / "general.bat"
    script_b = tmp_path / "general ALT.bat"
    script_a.write_text("@echo off\n", encoding="utf-8")
    script_b.write_text("@echo off\n", encoding="utf-8")
    settings = SettingsStore(tmp_path / "settings.json")
    service = FakeZapretService([script_a, script_b], script_a)
    controller = ZapretController(AppState(), settings, AppLogger(path=tmp_path / "app.log"), service, FakeZapretHealth(service))
    controller._sleep_or_cancel = lambda _seconds: False

    def progress(message: str) -> None:
        if message.startswith("zapret_test_row:"):
            controller.cancel_test()

    rows = controller.test_all_scripts(progress)

    assert len(rows) == 1
    assert settings.section("zapret")["selected_script"] is None
    assert service.running is False


def test_zapret_test_all_restores_running_script(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("cheburnet.app.controllers.zapret_controller.is_admin", lambda: True)
    monkeypatch.setattr("cheburnet.app.controllers.zapret_controller.time.sleep", lambda _seconds: None)
    script_a = tmp_path / "general.bat"
    script_b = tmp_path / "general ALT.bat"
    script_a.write_text("@echo off\n", encoding="utf-8")
    script_b.write_text("@echo off\n", encoding="utf-8")
    state = AppState()
    state.set_zapret_status(ZapretStatus.RUNNING)
    settings = SettingsStore(tmp_path / "settings.json")
    settings.update({"zapret": {"selected_script": str(script_a), "mode": "manual", "enabled": True}})
    service = FakeZapretService([script_a, script_b], script_b)
    service.running = True
    controller = ZapretController(state, settings, AppLogger(path=tmp_path / "app.log"), service, FakeZapretHealth(service))
    controller._sleep_or_cancel = lambda _seconds: False

    controller.test_all_scripts()

    assert service.running is True
    assert service.current == script_a
    assert state.zapret_status == ZapretStatus.RUNNING
