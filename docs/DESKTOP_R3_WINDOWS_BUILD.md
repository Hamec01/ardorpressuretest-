# R3 Desktop 1.1.0 — Windows build and acceptance

Этот документ относится к build-kit R3 Desktop 1.1.0. Сборка выполняется только на Windows 10/11 в новой папке, не поверх действующей установки.

## 1. Сборка

Откройте обычный `cmd.exe` в распакованной папке и выполните:

```bat
INSTALL.bat
BUILD_APP.bat
```

Ожидаемый результат: `dist\WIKA CPG1500 Processor.exe`; `BUILD_APP.bat` заканчивается без `[ERROR]` и выполняет встроенный `--version` smoke-check.

## 2. Проверка auth без синхронизации данных

В том же `cmd.exe`:

```bat
.venv\Scripts\python.exe scripts\desktop_auth_smoke.py
```

Введите username и password в интерактивных запросах. Пароль скрыт и не передаётся через аргументы или environment. Скрипт создаёт desktop-session, проверяет Windows Credential Manager и обязательную refresh rotation. Очередь sync и бизнес-данные не читаются и не отправляются.

Успешный результат:

```text
DESKTOP_LOGIN_OK: True
KEYRING_REFRESH_ROTATION_OK: True
BUSINESS_SYNC_PERFORMED: False
```

## 3. Portable/installer package

После успешной проверки:

```bat
CREATE_RELEASE_PACKAGE.bat
```

Inno Setup создаётся только если Inno Setup 6 установлен. Portable executable доступен и без Inno Setup.

## 4. Установка и ручная проверка

1. Сохраните резервную копию существующих `config.json`, `output/` и локальной sync queue.
2. Установите новую версию либо запустите portable build из отдельной папки.
3. Убедитесь, что окно показывает версию `1.1.0`.
4. Откройте существующие локальные материалы и убедитесь, что offline processing работает без сети.
5. Не закрывайте старую установку до завершения проверки.

Маршруты `/sync/*` на сервере остаются в переходном режиме до отдельного подтверждения установленного клиента. Публикация GitHub Release и удаление legacy/no-auth совместимости не входят в эту операцию.
