# ADR-010: Реализация R3 — серверные browser/desktop-сессии

**Status:** Accepted; implemented in code, staging rollout pending
**Decision date:** 2026-09-24
**Code baseline:** `feature/r3b-browser-session-api` @ `798d46037db56217ba387eb50034424760ba8791`
**Depends on:** [ADR-005](ADR-005-auth-session-model.md), R2 integration baseline `e2da9fc`

## 1. Контекст и границы

ADR-005 утвердил browser-cookie и desktop-device session model. Этот ADR фиксирует фактически реализованный контракт R3, порядок безопасного включения и временные ограничения переходного периода.

R3 не закрывает все business routes: полный endpoint/capability audit остаётся R4. В частности, зависимости auth на `/api/v1/sync/*` не включаются до фактического распространения и проверки нового desktop-клиента. Last-admin guard также остаётся частью будущих account-management routes: в текущем API нет маршрута деактивации или смены роли пользователя, на который его можно корректно навесить.

## 2. Схема данных

Additive migration `d3fc3cb2ef8b` (`down_revision = 2327325e8143`) добавляет:

- `users.must_change_password BOOLEAN NOT NULL`, существующие строки получают `false`, временный server default удаляется после backfill;
- таблицу `sessions` для browser и desktop channel;
- только SHA-256 hashes session/refresh/CSRF secrets; исходные секреты в БД не сохраняются;
- ограничения channel/CSRF/rotation/revocation/hash length/expiry и индексы для token lookup и активных сессий;
- FK `sessions.user_id -> users.id` без cascade delete.

Миграция не меняет поведение старого приложения и допускает rollback API без downgrade БД.

## 3. Password crypto

- Новые hashes: Argon2id, `m=12288 KiB`, `t=3`, `p=1`.
- Legacy PBKDF2 остаётся только для проверки. После успешной проверки пароль перехешируется в Argon2id в той же бизнес-транзакции.
- Новый пароль: от 6 до 128 Unicode codepoints; значение не обрезается и не нормализуется.
- Неизвестный username проходит dummy Argon2 verification и получает тот же ответ 401, что и неверный пароль.
- Rate limit проверяется до дорогого Argon2: пять неуспешных попыток на нормализованный username за 15 минут разрешены, следующая получает 429 и `Retry-After`.

## 4. Browser session

Browser session использует два host-only cookie с `Path=/`, без `Domain`:

- server mode: `__Host-ardor_session` (`Secure`, `HttpOnly`, `SameSite=Lax`);
- server mode: `__Host-ardor_csrf` (`Secure`, не HttpOnly, `SameSite=Lax`);
- explicit local/test mode использует имена без `__Host-` и допускает non-Secure cookie для локальной разработки.

Session secret и CSRF secret генерируются независимо. На каждом unsafe cookie-authenticated request backend требует:

1. точный `Origin == ARDOR_PUBLIC_ORIGIN`;
2. `X-CSRF-Token`;
3. совпадение SHA-256 header token с `sessions.csrf_token_hash` через constant-time compare.

CSRF применяется глобально через authentication dependencies ко всем unsafe routes, использующим `require_role` или `require_authenticated_user`, а не только к `/auth/*`.

Browser idle lifetime — 12 часов, absolute lifetime — 30 дней. `last_seen_at` обновляется не чаще одного раза в пять минут. Невалидная browser session возвращает внутренний marker, который middleware преобразует в удаление обоих stale cookies. Посторонний 401, например неверный current password, cookies не удаляет.

## 5. Безопасный переход web

Login устанавливает browser cookies только при одновременном выполнении двух условий:

- `Origin` точно равен `ARDOR_PUBLIC_ORIGIN`;
- клиент прислал `X-Ardor-Session-Mode: browser`.

Это rollout gate. Старый web, не отправляющий opt-in header, продолжает получать legacy bearer response и не получает cookies. Новый web отправляет header, хранит auth только в cookies, использует `credentials: same-origin`, добавляет CSRF header только к unsafe methods и не использует `localStorage`/`Authorization`.

Если `must_change_password=true`, UI блокирует рабочее приложение до успешной смены пароля, оставляя доступным logout.

## 6. Desktop session

- Desktop login создаёт DB-backed session на 30 дней, возвращает opaque refresh secret и access JWT на 15 минут.
- Access JWT требует `typ=desktop_access`, `sub`, `sid`, integer `iat/exp`, HS256 header и ровно 900 секунд lifetime.
- Каждый authenticated desktop request проверяет `sid` по PK в БД, поэтому revoke действует немедленно.
- Refresh secret обязательно ротируется conditional update. Предыдущий hash хранится только для reuse detection.
- Повторное предъявление предыдущего refresh secret отзывает сессию с `reuse_detected`; access JWT этой сессии сразу перестаёт работать.
- Access token живёт только в памяти desktop-процесса; refresh secret — только в OS keyring. Ни один из них не пишется в config, manifest или SQLite queue.
- 401 сохраняет локальную очередь и требует повторный вход; данные не удаляются и не помечаются synced.

## 7. Authentication precedence и переходный bearer

Порядок проверки:

1. если browser cookie присутствует, он authoritative; при ошибке fallback на bearer запрещён;
2. без cookie проверяется строгий desktop JWT и его live session;
3. затем временно допускается legacy bearer JWT без `typ`/`sid`.

Legacy bearer невозможно отозвать server-side: logout очищает клиентское состояние, но такой токен остаётся действительным до естественного expiry. Этот путь удаляется отдельным этапом только после подтверждённого перехода web и desktop.

## 8. Auth endpoints

| Endpoint | Доступ | Назначение |
|---|---|---|
| `POST /api/v1/auth/login` | public | rate-limited login; browser cookie только через rollout gate |
| `POST /api/v1/desktop/login` | public | desktop session + access/refresh credentials |
| `POST /api/v1/desktop/token/refresh` | opaque refresh secret | обязательная rotation/reuse detection |
| `GET /api/v1/auth/me` | authenticated admin/foreman/viewer | включает `must_change_password` |
| `POST /api/v1/auth/logout` | authenticated | отзывает текущую DB-backed session; разрешён при must-change |
| `POST /api/v1/auth/change-password` | authenticated | меняет пароль, отзывает остальные sessions, текущую browser session ротирует |
| `GET /api/v1/auth/sessions` | authenticated admin/foreman/viewer | только собственные sessions |
| `DELETE /api/v1/auth/sessions/{id}` | authenticated admin/foreman/viewer | только собственная session, guarded update |
| `GET /api/v1/auth/users` | admin only | Foreman получает 403 |

При `must_change_password=true` разрешены только точные пути `/api/v1/auth/me`, `/api/v1/auth/logout`, `/api/v1/auth/change-password`.

## 9. Конфигурация и fail-closed startup

В server mode обязательна `ARDOR_PUBLIC_ORIGIN`: canonical HTTPS origin без path/query/fragment/credentials. Для staging утверждено `https://84-247-130-242.sslip.io`.

Оба staging Compose-файла используют `${ARDOR_PUBLIC_ORIGIN:?ARDOR_PUBLIC_ORIGIN must be set}`. Отсутствующая переменная останавливает `docker compose config` до пересоздания контейнера. Cookie Secure в server mode не выводится из request scheme и не может быть выключен конфигурацией.

## 10. Rollout

Rollout выполняется отдельным разрешённым live-этапом:

1. read-only gates: clean verified commit, current Alembic head, health, container image/`StartedAt`, HTTPS same-origin path;
2. backup Postgres и проверка `pg_restore -l`;
3. добавить только `ARDOR_PUBLIC_ORIGIN` в защищённый live `.env`;
4. `docker compose ... config --quiet` с обязательным `--env-file`;
5. применить additive migration `d3fc3cb2ef8b` одноразовым контейнером;
6. backend-first deploy нового API image; старый web продолжает legacy bearer flow и не получает cookies;
7. проверить health, legacy login и новые auth contracts;
8. deploy нового web image;
9. реальный browser click-through по HTTPS: cookie acceptance, `/me`, unsafe CSRF, logout, stale-cookie cleanup, must-change flow;
10. отдельно собрать, установить и проверить desktop build; только после этого разрешается закрывать `/sync/*`.

## 11. Rollback

- До web switch: вернуть предыдущий API image; additive schema остаётся и не мешает старому API.
- После web switch: сначала вернуть предыдущий web image, затем при необходимости API image.
- Миграцию по умолчанию не downgrade: после появления session rows downgrade удаляет данные и становится destructive operation.
- Live `.env`/Compose восстанавливаются только из заранее проверенной закрытой backup-копии либо точечной обратной правкой.

## 12. Отложенные пункты

- R4: закрыть и проматрицировать business routes, включая F03.
- Desktop rollout: не добавлять auth dependency на `/sync/*`, пока новый build не установлен и не проверен.
- Account management/R7: TOCTOU-safe last-admin guard на deactivate/demote routes.
- Infra: закрыть прямой внешний доступ к `:8000`/`:8080` за Caddy; подтвердить firewall/Docker rules с необходимыми правами.
- После завершения перехода: удалить acceptance legacy bearer JWT и связанные compatibility paths.

## 13. Verification baseline

На code baseline `798d460`:

- backend/desktop suite: `515 passed`, три известных warning без новых failures;
- production web build: успешно;
- throwaway PostgreSQL: конкурентный login rate-limit и desktop refresh reuse/revocation подтверждены;
- staging preflight read-only: live Alembic `2327325e8143`, новый code head `d3fc3cb2ef8b`; отсутствие `ARDOR_PUBLIC_ORIGIN` корректно даёт Compose exit 1 до любых live-изменений;
- staging остаётся на прежних images, health 200/200; R3 migration/deploy ещё не выполнялись.
