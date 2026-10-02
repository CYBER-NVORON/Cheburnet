# Changelog

## v1.0.2 - 2026-07-31

### Fixed

- Исправлен парсинг параметра `spx` для профилей VLESS REALITY (теперь корректно декодируется url-encoded значение и передается в `spider_x`).
- Исправлен маппинг параметра `fp` (fingerprint) для uTLS: теперь он передается 1-в-1 как указано в ссылке профиля, а если отсутствует — подставляется `"chrome"`.

## v1.0.1 - 2026-07-30

### Added

- Добавлен выбор темы в настройках и обновлена общая система оформления интерфейса.
- На странице Zapret добавлены расширенные параметры управления сервисом.

### Changed

- Настройки, главные экраны и стили приведены к новой структуре тем.
- Обновлена страница обновлений: добавлен более наглядный индикатор проверки версий.
- Улучшены прокрутка, адаптивные раскладки и логика проверки версий.
- При запуске теперь очищаются старые загрузки и распакованные файлы sing-box и Zapret.

### Removed

- Убраны устаревшие списки профилей и связанные с ними элементы UI.

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
