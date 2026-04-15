# Cheburnet v0.2.0

## Русский

UX-релиз: приложение стало проще для обычного пользователя.

### Главное

- Новый минималистичный главный экран: только `YouTube и Discord`, `VPN`, `Туннелирование`.
- Первый запуск теперь объясняет работу приложения простыми шагами.
- Если режим ещё не настроен, Cheburnet открывает понятное окно настройки:
  - zapret: выбрать папку или скачать последнюю версию;
  - VPN: скачать клиент или добавить конфиг;
  - туннелирование: скачать sing-box, добавить WireGuard config, открыть список сайтов.
- VPN и туннелирование больше не конфликтуют: включение одного выключает другое.
- Настройки собраны в одном месте: zapret-конфиг, проверка всех конфигов, VPN-профили, прямые сайты.
- Добавлен `direct-sites.txt` для доменов, которые идут напрямую.
- Шестерня и переключатели стали сглаженными, без пиксельного Canvas-рисования.
- Окно стало адаптивным: можно уменьшать/растягивать, настройки перестраиваются под узкую ширину.
- Сообщение при остановке zapret теперь нормальное, если `winws.exe` уже выключен.

### Файл релиза

- `Cheburnet.exe`

## English

UX release: Cheburnet is now easier for non-technical users.

### Highlights

- New minimal main screen with only three controls: `YouTube and Discord`, `VPN`, `Tunneling`.
- First-run guide now explains setup in simple steps.
- If a mode is not configured yet, Cheburnet opens a friendly setup dialog:
  - zapret: choose a folder or download the latest version;
  - VPN: download a client or add a config;
  - tunneling: download sing-box, add a WireGuard config, open the direct-sites list.
- VPN and tunneling no longer conflict: enabling one disables the other.
- Settings now collect zapret config selection, config testing, VPN profiles and direct sites in one place.
- Added `direct-sites.txt` for domains that should go direct.
- Gear icon and switches are now antialiased instead of pixelated Canvas drawings.
- Window layout is responsive and can be resized more comfortably.
- Stopping zapret now shows a friendly message when `winws.exe` is already stopped.

### Release Asset

- `Cheburnet.exe`
