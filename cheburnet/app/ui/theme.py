from __future__ import annotations

THEMES: dict[str, dict[str, str]] = {
    "control_deck": {
        "name": "Control Deck",
        "bg": "#090A12",
        "sidebar": "#0D0E18",
        "card": "#171824",
        "card_inner": "#202130",
        "border": "#303244",
        "text": "#F5F6FF",
        "muted": "#9B9EAF",
        "accent": "#7C5CFF",
        "accent2": "#5EF0AA",
        "danger": "#FF5573",
        "warning": "#FFD166",
        "input": "#11121D",
        "hover": "#252739",
    },
    "graphite_mint": {
        "name": "Graphite Mint",
        "bg": "#0A1010",
        "sidebar": "#0D1515",
        "card": "#14201F",
        "card_inner": "#1B2A28",
        "border": "#2E4642",
        "text": "#F1FFF9",
        "muted": "#92AEA5",
        "accent": "#2FE6A0",
        "accent2": "#6EE7F9",
        "danger": "#FF647C",
        "warning": "#F7C85A",
        "input": "#0E1918",
        "hover": "#213431",
    },
    "northern_blue": {
        "name": "Northern Blue",
        "bg": "#07101E",
        "sidebar": "#0A1526",
        "card": "#111E33",
        "card_inner": "#172842",
        "border": "#29415F",
        "text": "#EEF6FF",
        "muted": "#99ABC3",
        "accent": "#5AA7FF",
        "accent2": "#66E0D2",
        "danger": "#FF6685",
        "warning": "#F4C45E",
        "input": "#0B1729",
        "hover": "#1C3354",
    },
    "signal_amber": {
        "name": "Signal Amber",
        "bg": "#11100B",
        "sidebar": "#17150E",
        "card": "#221F15",
        "card_inner": "#2C281B",
        "border": "#4A422B",
        "text": "#FFF8E8",
        "muted": "#B4A98E",
        "accent": "#FFB84D",
        "accent2": "#5EF0AA",
        "danger": "#FF5E5E",
        "warning": "#FFE070",
        "input": "#19170F",
        "hover": "#342F20",
    },
}

THEME_ALIASES = {
    "one_dash": "control_deck",
    "dark": "control_deck",
}

COLORS = dict(THEMES["control_deck"])


def theme_names() -> list[tuple[str, str]]:
    return [(key, value["name"]) for key, value in THEMES.items()]


def apply_theme(key: str | None) -> dict[str, str]:
    normalized = THEME_ALIASES.get(str(key or "control_deck"), str(key or "control_deck"))
    palette = THEMES.get(normalized, THEMES["control_deck"])
    COLORS.clear()
    COLORS.update(palette)
    return COLORS
