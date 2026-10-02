import sys
import logging
from pathlib import Path
from cheburnet.app.services.free_configs_service import FreeConfigsService
from cheburnet.app.services.mihomo_config_builder import MihomoConfigBuilder
from cheburnet.app.services.mihomo_service import MihomoService

logging.basicConfig(level=logging.INFO)

link = "vless://2ebc0318-fb20-4930-a221-8b52dcec7983@89.125.140.215:443?encryption=none&flow=xtls-rprx-vision&fp=firefox&pbk=NzY9iAt-oCOg7yYOMWDsg-xGuWTzXvukYmNKZg0aWQM&security=reality&sid=d111ad8650ec&sni=www.amd.com&spx=%2Fee21da4dc0055b6&type=tcp#HLK-VLESS-PC"

svc = FreeConfigsService()
profile = svc.parse_link(link)
if not profile:
    print("Failed to parse link")
    sys.exit(1)

print("Proxy Dict:", profile.outbound)

builder = MihomoConfigBuilder()
settings = {"routing_mode": "full_vpn", "vpn": {"dns_protection": True}}
config_path = builder.build_config(profile, settings, "test_config.yaml")

print("Built config at", config_path)
with open(config_path, "r", encoding="utf-8") as f:
    print(f.read())

mihomo = MihomoService()
print("Downloading Mihomo...")
binary = mihomo.ensure_installed()
print("Downloaded to", binary)

print("Checking config...")
res = mihomo.check_config(binary, config_path)
print("Check:", res.text)
