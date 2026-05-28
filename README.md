# CheburNet

CheburNet - Windows desktop app на Python 3.11+ и PySide6 для VPN через `sing-box` и Flowseal `zapret-discord-youtube`.

## Возможности

- VPN-профили: VLESS, VMess, Trojan, Shadowsocks, Hysteria2 URI, импорт `.txt` списков/URL списков и WireGuard `.conf`.
- WireGuard после импорта хранится внутри профиля, исходный `.conf` больше не нужен.
- Режимы VPN: `Обычный VPN`, `Туннелирование`, `Выключен`.
- Zapret: скачивание Flowseal release, выбор своей папки, выбор `.bat` по умолчанию, скрытый прямой запуск `winws.exe`.
- Тест всех Zapret-конфигов с потоковым добавлением результатов и возможностью остановки.
- Настройки Zapret: Game filter, IPSet filter, Auto-update check.
- Автозапуск VPN/Zapret при старте приложения.
- Автопереключение на другой VPN-профиль, если выбранный не работает.
- Логи пишутся в `%APPDATA%/CheburNet/logs/cheburnet.log`.

## Режимы

- `full_vpn` / Обычный VPN: основной трафик через VPN, direct-исключения из правил идут напрямую.
- `smart_split` / Туннелирование: YouTube/Discord идут напрямую через Zapret, остальное через VPN.
- `zapret_only` / Выключен: VPN не запускается; при включенном Zapret YouTube/Discord идут через Zapret.

`DNS protection` включает строгую маршрутизацию DNS в TUN. `Kill switch` дополнительно убирает direct-исключения и принудительно включает strict route.

## Запуск из исходников

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python run.py
```

Для VPN/TUN и Zapret нужны права администратора. На Windows приложение пытается перезапуститься с UAC автоматически.

## Данные приложения

```text
%APPDATA%/CheburNet/
  settings.json
  profiles.json
  logs/cheburnet.log
  generated/singbox_config.json
  tools/sing-box/
  tools/zapret/
```

Путь можно переопределить переменной `CHEBURNET_HOME`.

## Тесты

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Сборка

Сборка Windows x64 делается в onedir-формате:

```powershell
python -m pip install -r requirements-dev.txt
.\build_scripts\build_exe.ps1
```

Результат:

```text
dist\CheburNet\CheburNet.exe
```

`sing-box` и `zapret` не входят в репозиторий и скачиваются приложением в пользовательскую папку данных.

## Платформы

| Платформа | Статус | Комментарий |
| --- | --- | --- |
| Windows x64 | поддерживается | основной релизный вариант |
| Windows x32 | не поддерживается | PySide6/Qt6 и зависимости ориентированы на 64-bit; отдельная 32-bit сборка сейчас нецелесообразна |
| Linux x64 | не поддерживается текущей сборкой | нужен отдельный backend для прав, TUN, путей, sing-box и Zapret; текущий Zapret-код запускает Windows `.bat`/`winws.exe` |

PyInstaller не кросс-компилирует: Windows-сборку надо собирать на Windows, Linux-сборку - на Linux.

## Публикация GitHub Release

### Через браузер без GitHub CLI

```powershell
.\build_scripts\package_release.ps1 -Tag v0.4.0 -Platform windows-x64
```

Дальше открыть GitHub в браузере:

1. `Releases` -> `Draft a new release`.
2. Создать tag `v0.4.0`.
3. Вставить текст из `RELEASE_NOTES.md`.
4. Загрузить файл `dist\CheburNet-v0.4.0-windows-x64.zip`.
5. Нажать `Publish release`.

### Через GitHub CLI

Нужны GitHub CLI и авторизация:

```powershell
winget install --id GitHub.cli -e
gh auth login
```

Создать архив и релиз:

```powershell
.\build_scripts\publish_github_release.ps1 -RepoName Cheburnet -Visibility public -Tag v0.4.0 -Platform windows-x64
```

Скрипт собирает `dist\CheburNet`, архивирует папку в `dist\CheburNet-v0.4.0-windows-x64.zip`, пушит тег и загружает архив в GitHub Release.

Перед релизом пройти чеклист: [docs/MANUAL_TESTING.md](docs/MANUAL_TESTING.md).
