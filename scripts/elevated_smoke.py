from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cheburnet.app.core.config import SettingsStore
from cheburnet.app.core.paths import logs_dir
from cheburnet.app.core.system import is_admin
from cheburnet.app.models.profile import RoutingMode
from cheburnet.app.services.healthcheck_service import HealthcheckService
from cheburnet.app.services.profile_store import ProfileStore
from cheburnet.app.services.singbox_config_builder import SingBoxConfigBuilder
from cheburnet.app.services.singbox_service import SingBoxService
from cheburnet.app.services.wireguard_importer import WireGuardImporter
from cheburnet.app.services.zapret_service import ZapretService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", default="")
    parser.add_argument("--skip-vpn", action="store_true")
    parser.add_argument("--skip-zapret", action="store_true")
    args = parser.parse_args()

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    result_path = Path(args.result) if args.result else logs_dir() / f"elevated-smoke-{timestamp}.json"
    text_log = result_path.with_suffix(".log")
    result: dict[str, object] = {"ok": False, "steps": []}
    output_counts: dict[str, int] = {}

    def step(name: str, ok: bool, detail: str = "") -> None:
        if name.endswith("output"):
            output_counts[name] = output_counts.get(name, 0) + 1
            if output_counts[name] > 40:
                return
        item = {"name": name, "ok": ok, "detail": detail}
        result["steps"].append(item)  # type: ignore[index]
        with text_log.open("a", encoding="utf-8") as file:
            file.write(f"{time.strftime('%H:%M:%S')} {'OK' if ok else 'FAIL'} {name}: {detail}\n")

    singbox = SingBoxService()
    zapret: ZapretService | None = None

    try:
        admin = is_admin()
        step("admin", admin, "Запущено от администратора" if admin else "Нет прав администратора")
        if not admin:
            raise RuntimeError("Smoke должен быть запущен от администратора.")

        settings = SettingsStore()
        profiles = ProfileStore()
        selected = profiles.get(settings.get("selected_profile_id")) or (profiles.all()[0] if profiles.all() else None)
        step("profile", selected is not None, selected.name if selected else "Профиль не выбран")
        if selected is None:
            raise RuntimeError("Нет выбранного профиля.")

        if not args.skip_vpn:
            binary = singbox.ensure_installed(progress=lambda message: step("sing-box download", True, message))
            version = singbox.version(binary)
            step("sing-box version", bool(version), version or str(binary))

            mode = RoutingMode(str(settings.get("routing_mode", RoutingMode.FULL_VPN.value)))
            if mode == RoutingMode.ZAPRET_ONLY:
                mode = RoutingMode.FULL_VPN
            config_path = SingBoxConfigBuilder(WireGuardImporter()).build(selected, settings.data, mode, version)
            step("sing-box config", config_path.exists(), str(config_path))

            check = singbox.check_config(binary, config_path)
            step("sing-box check", check.ok, check.text or "OK")
            if not check.ok:
                raise RuntimeError(check.text or "sing-box check failed")

            singbox.start(binary, config_path, on_output=lambda line: step("sing-box output", True, line))
            step("sing-box start", singbox.is_running(), f"running={singbox.is_running()}")
            health = HealthcheckService().internet_check(timeout=12)
            step("vpn internet health", health.status.value == "ok", f"{health.status.value}: {health.detail}")
            singbox.stop()
            step("sing-box stop", not singbox.is_running(), f"running={singbox.is_running()}")

        if not args.skip_zapret:
            zapret = ZapretService(settings.section("zapret").get("install_dir") or None)
            root = zapret.find_root()
            scripts = zapret.available_scripts()
            step("zapret folder", bool(root and root.exists()), str(root) if root else "not found")
            step("zapret scripts", bool(scripts), ", ".join(script.name for script in scripts[:5]))
            if scripts:
                selected_script = None
                configured = settings.section("zapret").get("selected_script")
                if configured:
                    configured_path = Path(str(configured))
                    selected_script = configured_path if configured_path.exists() else None
                candidates = scripts if settings.section("zapret").get("mode", "auto") == "auto" else [selected_script or scripts[0]]
                selected_ok = False
                for candidate in candidates:
                    try:
                        zapret.start_script(candidate, on_output=lambda line: step("zapret output", True, line))
                        step("zapret start", zapret.is_running(), candidate.name)
                        checks = HealthcheckService().check_youtube_discord()
                        for name, check_result in checks.items():
                            step(f"{name} health {candidate.name}", check_result.status.value == "ok", f"{check_result.status.value}: {check_result.detail}")
                        if all(check_result.status.value == "ok" for check_result in checks.values()):
                            selected_ok = True
                            step("zapret auto selected", True, candidate.name)
                            break
                    except Exception as exc:
                        step(f"zapret candidate {candidate.name}", False, str(exc))
                    finally:
                        try:
                            zapret.stop()
                        except Exception as exc:
                            step("zapret stop", False, str(exc))
                step("zapret auto result", selected_ok, "found working script" if selected_ok else "no script passed YouTube+Discord")
                step("zapret stop", not zapret.is_running(), f"running={zapret.is_running()}")

        optional_prefixes = ("youtube health", "discord health")
        result["ok"] = all(
            bool(item["ok"])
            for item in result["steps"]  # type: ignore[index]
            if not str(item["name"]).startswith(optional_prefixes)
        )
    except Exception as exc:
        step("exception", False, f"{exc}\n{traceback.format_exc()}")
    finally:
        try:
            singbox.stop()
        except Exception:
            pass
        try:
            if zapret:
                zapret.stop()
        except Exception:
            pass
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(result_path)

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
