from __future__ import annotations

APP_NAME = "CheburNet"
APP_VERSION = "1.0.1"

CHEBURNET_REPO = "CYBER-NVORON/Cheburnet"
CHEBURNET_RELEASE_API = f"https://api.github.com/repos/{CHEBURNET_REPO}/releases/latest"

SING_BOX_REPO = "SagerNet/sing-box"
SING_BOX_RELEASE_API = f"https://api.github.com/repos/{SING_BOX_REPO}/releases/latest"

ZAPRET_REPO = "Flowseal/zapret-discord-youtube"
ZAPRET_RELEASE_API = f"https://api.github.com/repos/{ZAPRET_REPO}/releases/latest"
ZAPRET_VERSION_URL = f"https://raw.githubusercontent.com/{ZAPRET_REPO}/main/.service/version.txt"
ZAPRET_IPSET_URL = f"https://raw.githubusercontent.com/{ZAPRET_REPO}/refs/heads/main/.service/ipset-service.txt"
ZAPRET_HOSTS_URL = f"https://raw.githubusercontent.com/{ZAPRET_REPO}/refs/heads/main/.service/hosts"

YOUTUBE_DISCORD_DOMAINS = [
    "youtube.com",
    ".youtube.com",
    "youtu.be",
    ".youtu.be",
    "ytimg.com",
    ".ytimg.com",
    "googlevideo.com",
    ".googlevideo.com",
    "ggpht.com",
    ".ggpht.com",
    "discord.com",
    ".discord.com",
    "discord.gg",
    ".discord.gg",
    "discordapp.com",
    ".discordapp.com",
    "discordapp.net",
    ".discordapp.net",
]

DEFAULT_DIRECT_DOMAINS = [".ru", ".рф", ".su", "vk.com"]

FREE_CONFIG_SCHEMES = ("vless://", "vmess://", "trojan://", "ss://", "hysteria2://", "hy2://")

TRUSTED_TOOLS_DIR_NAME = "tools"
