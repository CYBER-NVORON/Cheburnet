# Changelog

## v0.2.0 - 2026-04-15

### Added

- Minimal main screen with three clear toggles: YouTube/Discord, VPN and tunneling.
- First-run guide focused on basic user setup.
- Setup dialogs for zapret, VPN and tunneling when a mode is enabled before it is configured.
- Settings screen for zapret config selection, VPN profile management and direct-site list editing.
- Smooth generated icons and switches through Pillow.
- Responsive window sizing with a smaller minimum size and stacked settings layout on narrow windows.
- `direct-sites.txt` for user-editable direct domains.

### Changed

- Reduced technical text on the main screen.
- VPN and tunneling are now mutually exclusive from the main controls.
- Zapret stop messages are now user-friendly when `winws.exe` is already stopped.
- Closing the app still stops zapret, sing-box tunnel and the selected VPN profile.

## v0.1.0 - 2026-04-15

### Added

- Windows GUI app for managing zapret, VPN profiles and rule-based site tunneling.
- Flowseal `zapret-discord-youtube` integration with strategy discovery, download and testing.
- Hidden direct `winws.exe` launch from parsed zapret strategy files.
- WireGuard/OpenVPN/WARP system profile management and installer buttons.
- Rule-based site tunnel via `sing-box` TUN with WireGuard `.conf` support.
- Direct rules for `.ru`, `.рф`, `.su`, user domains, CIDR ranges and selected processes.
- RU IPv4 range downloader from RIPE delegated stats.
- Dark/light theme, animated header, persistent settings and Windows `.exe` build.
