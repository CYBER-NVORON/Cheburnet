# Cheburnet v0.1.0

## Русский

Первый публичный релиз Cheburnet.

### Главное

- GUI-приложение для Windows на Python/Tkinter.
- Zapret для YouTube/Discord через Flowseal `zapret-discord-youtube`.
- Проверка zapret-стратегий и выбор лучшего конфига.
- Скрытый запуск `winws.exe` без видимого окна `cmd`.
- Rule-based туннель сайтов через `sing-box`:
  - `.ru`, `.рф`, `.su` и пользовательские исключения идут напрямую;
  - остальной трафик идёт через WireGuard endpoint;
  - YouTube/Discord остаются direct, чтобы их обрабатывал zapret.
- WireGuard/OpenVPN/WARP профили и кнопки установки официальных клиентов.
- Автоскачивание `sing-box`.
- Сборка в `Cheburnet.exe` с иконкой, metadata и UAC manifest.

### Файл релиза

- `Cheburnet.exe`

## English

First public Cheburnet release.

### Highlights

- Windows Python/Tkinter GUI app.
- YouTube/Discord zapret integration through Flowseal `zapret-discord-youtube`.
- Zapret strategy testing and best config selection.
- Hidden direct `winws.exe` launch without a visible `cmd` window.
- Rule-based site tunnel through `sing-box`:
  - `.ru`, `.рф`, `.su` and user exclusions go direct;
  - the rest goes through the WireGuard endpoint;
  - YouTube/Discord stay direct so zapret can handle them.
- WireGuard/OpenVPN/WARP profiles and official client installer buttons.
- `sing-box` download from the app.
- `Cheburnet.exe` build with icon, metadata and UAC manifest.

### Release Asset

- `Cheburnet.exe`
