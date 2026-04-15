# Cheburnet

![Windows](https://img.shields.io/badge/Windows-10%2F11-1677c9)
![Python](https://img.shields.io/badge/Python-3.11%2B-0f9f6e)
![License](https://img.shields.io/badge/License-MIT-101820)

**RU:** Cheburnet - Windows-приложение для управления zapret, VPN-профилями и rule-based туннелированием сайтов.  
**EN:** Cheburnet is a Windows app for managing zapret, VPN profiles and rule-based site tunneling.

> Проект не содержит сторонние бинарники в репозитории. Приложение скачивает upstream-инструменты явно из интерфейса.
>
> The repository does not commit third-party binaries. The app downloads upstream tools explicitly from the UI.

## Русский

### Что умеет

- Запуск и тестирование Flowseal `zapret-discord-youtube` для YouTube и Discord.
- Скрытый запуск `winws.exe` без видимого окна `cmd`.
- Скачивание latest zapret release из интерфейса.
- WireGuard/OpenVPN/WARP профили и кнопки установки официальных клиентов.
- Точный режим “сайты по правилам” через `sing-box` TUN:
  - `.ru`, `.рф`, `.su` и свои домены идут напрямую;
  - остальной трафик идёт через WireGuard endpoint;
  - YouTube/Discord идут напрямую, чтобы их обрабатывал zapret.
- Загрузка RU IPv4 диапазонов из RIPE delegated stats.
- Тёмная/светлая тема, анимированная шапка, сохранение настроек.
- Windows `.exe` сборка с иконкой и UAC manifest.

### Быстрый старт из exe

1. Скачайте `Cheburnet.exe` из релиза.
2. Запустите приложение. Windows запросит права администратора один раз.
3. Во вкладке `YouTube / Discord` скачайте или выберите папку Flowseal zapret.
4. Нажмите `Тест всех`, затем запустите лучший конфиг.
5. Во вкладке `VPN` импортируйте WireGuard `.conf`.
6. Во вкладке `Туннель сайтов` скачайте `sing-box`, сгенерируйте конфиг, проверьте его и запустите туннель.

Важно: для схемы `.ru/.рф/.su напрямую, остальное через VPN` не включайте системный WireGuard кнопкой `Подключить системный VPN`. `sing-box` сам поднимает WireGuard из `.conf`.

### Запуск из исходников

Требования:

- Windows 10/11.
- Python 3.11+.
- Права администратора для zapret, TUN, route changes и VPN-служб.

```powershell
python run.py
```

Основные Python-зависимости сейчас не требуются. Файл `requirements.txt` оставлен для будущих runtime-модулей.

### Сборка exe

```powershell
python -m pip install -r requirements-dev.txt
.\build_scripts\build_exe.ps1
```

Результат:

```text
dist\Cheburnet.exe
```

### Как устроено туннелирование

Обычный WireGuard/OpenVPN маршрутизирует по IP, а не по доменам. Поэтому Cheburnet использует `sing-box` как TUN/rule engine:

- DNS и SNI/HTTP sniffing используются для доменных правил.
- `domain_suffix`: `.ru`, `.рф`, `.su` -> `direct`.
- Пользовательские домены, CIDR и приложения -> `direct`.
- Финальное правило -> WireGuard endpoint.

OpenVPN остаётся системным VPN-профилем. Точный режим `final -> vpn` реализован для WireGuard `.conf`.

### Данные приложения

Настройки и скачанные компоненты:

```text
%APPDATA%\Cheburnet
```

Если папка недоступна, используется локальная `.cheburnet`. Можно переопределить путь через `CHEBURNET_HOME`.

## English

### Features

- Flowseal `zapret-discord-youtube` integration for YouTube and Discord.
- Hidden direct `winws.exe` launch without a visible `cmd` window.
- Latest zapret release download from the UI.
- WireGuard/OpenVPN/WARP profiles and official client installer buttons.
- Rule-based site tunnel through `sing-box` TUN:
  - `.ru`, `.рф`, `.su` and custom domains go direct;
  - everything else goes through the WireGuard endpoint;
  - YouTube/Discord stay direct so zapret can handle them.
- RU IPv4 range download from RIPE delegated stats.
- Dark/light theme, animated header and persistent settings.
- Windows `.exe` build with icon and UAC manifest.

### Quick Start From EXE

1. Download `Cheburnet.exe` from the release.
2. Run the app. Windows will ask for administrator rights once.
3. In `YouTube / Discord`, download or select the Flowseal zapret folder.
4. Click `Тест всех`, then start the best config.
5. In `VPN`, import a WireGuard `.conf`.
6. In `Туннель сайтов`, download `sing-box`, generate config, check it and start the tunnel.

Important: for `.ru/.рф/.su direct, everything else VPN`, do not start system WireGuard with `Подключить системный VPN`. `sing-box` runs WireGuard from the `.conf` itself.

### Run From Source

Requirements:

- Windows 10/11.
- Python 3.11+.
- Administrator rights for zapret, TUN, route changes and VPN services.

```powershell
python run.py
```

No runtime Python packages are required right now. `requirements.txt` is kept for future runtime modules.

### Build EXE

```powershell
python -m pip install -r requirements-dev.txt
.\build_scripts\build_exe.ps1
```

Output:

```text
dist\Cheburnet.exe
```

### Publish GitHub Release

```powershell
gh auth login
.\build_scripts\publish_github_release.ps1 -RepoName Cheburnet -Visibility public -Tag v0.1.0
```

The publish script creates the GitHub repository when `origin` does not exist,
pushes `main` and `v0.1.0`, then creates a GitHub release with `dist\Cheburnet.exe`.

### Tunneling Model

Plain WireGuard/OpenVPN routes by IP, not by domain. Cheburnet uses `sing-box` as the TUN/rule engine:

- DNS and SNI/HTTP sniffing are used for domain rules.
- `domain_suffix`: `.ru`, `.рф`, `.su` -> `direct`.
- Custom domains, CIDR ranges and apps -> `direct`.
- Final rule -> WireGuard endpoint.

OpenVPN remains a system VPN profile. Exact `final -> vpn` routing is implemented for WireGuard `.conf`.

### App Data

Settings and downloaded components:

```text
%APPDATA%\Cheburnet
```

If that path is unavailable, local `.cheburnet` is used. You can override the location with `CHEBURNET_HOME`.

## License

MIT. See [LICENSE](LICENSE).
