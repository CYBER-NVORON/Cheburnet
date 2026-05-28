from __future__ import annotations

APP_NAME = "CheburNet"
APP_VERSION = "0.2.0"

SING_BOX_REPO = "SagerNet/sing-box"
SING_BOX_RELEASE_API = f"https://api.github.com/repos/{SING_BOX_REPO}/releases/latest"

ZAPRET_REPO = "Flowseal/zapret-discord-youtube"
ZAPRET_RELEASE_API = f"https://api.github.com/repos/{ZAPRET_REPO}/releases/latest"

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
