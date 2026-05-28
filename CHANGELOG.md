# Changelog

## v0.4.0 - 2026-05-28

### Added

- Unified `VPN и серверы` section.
- VPN modes: normal VPN, tunneling, off.
- Manual VPN URI import, local list import and user-provided URL list import.
- Embedded WireGuard profile storage after `.conf` import.
- Zapret config selection with persistent default `.bat`.
- Zapret config testing with incremental table results and stop button.
- Hidden direct `winws.exe` launch parsed from Flowseal `.bat` files.
- Zapret filters: Game filter, IPSet filter, Auto-update check.
- VPN auto-failover when the selected profile fails.
- VPN/Zapret autostart from settings.

### Changed

- Removed mandatory bundled public GitHub config sources.
- Removed stale dashboard journal/quick-actions/traffic chart blocks.
- Improved table row selection, combo-box arrows and checkbox checkmarks.
- Health-check errors are logged without blocking modal popups.

### Removed

- Legacy single-file UI and old controller layer.
- Duplicate root PyInstaller spec and unused sample data.

## v0.3.0 - 2026-05-27

### Added

- Local sing-box VPN mode from VLESS/VMess/Trojan/Shadowsocks/Hysteria2 configs.
- PySide6 interface with sidebar, cards, settings, logs and updates.
- First-run sing-box downloader for the current OS/architecture.
- WireGuard endpoint-mode support through sing-box.
- Update screen for Zapret and sing-box.
