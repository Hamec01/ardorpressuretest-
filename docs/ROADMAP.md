# ARDOR Pressure Test — roadmap

**Статус:** Approved 1.0  
**Дата:** 2026-08-19  
**Главное правило:** следующий этап не начинается автоматически.

## Общая стратегия

Roadmap строит один проверяемый вертикальный продукт, а не одновременно desktop, сайт и server production. Сначала защищается существующая обработка, затем создаётся каноническая ревизия, после этого локальный sync, поиск, web-processing и Pressure Test Record.

## Этап 0. Утверждение основы

### Результат

- утверждены требования;
- утверждены правила агента;
- утверждена техническая архитектура;
- утверждён roadmap;
- открытые решения явно перечислены.

### Exit criteria

- заказчик прочитал документы;
- исправлены замечания;
- документы получают статус Approved 1.0;
- выбран первый implementation checkpoint.

## Этап 1. Baseline и полный аудит локального приложения

### Работы

- зафиксировать branch/commit/tag текущей рабочей версии;
- проверить зависимости и воспроизводимую установку;
- запустить весь pytest;
- проверить PyInstaller и Inno Setup;
- проверить реальные CSV разных форматов;
- проверить реальные output folders;
- сопоставить README, installer и фактическое поведение;
- составить migration inventory;
- убрать секреты/производственные данные из tracking;
- определить стратегию удаления binaries из будущих commits без опасного переписывания истории на этом этапе.

### Не входит

- новая UI;
- сервер;
- изменение PASS/FAIL.

### Exit criteria

- clean checkout запускается по инструкции;
- тесты зелёные;
- текущая portable build воспроизводима;
- известны все пути хранения;
- есть минимум три обезличенных real-world CSV fixtures;
- аудит утверждён.

## Этап 2. Каноническое ядро и атомарная ревизия

### Работы

- отделить orchestration от Tkinter;
- ввести DTO `TestInput`, `RevisionManifest`, `RevisionBuildResult`;
- нормализовать Log No.;
- добавить bundle and operator fields;
- классифицировать фотографии;
- включить исходный CSV в комплект;
- создать revision directory;
- рассчитать SHA-256;
- устранить двойные дефисы и дубликаты фото;
- обеспечить backward-compatible desktop flow;
- обновить installer paths and README.

### Exit criteria

- один запуск создаёт один самостоятельный комплект;
- повторный запуск создаёт новую ревизию;
- ни один файл не смешивается;
- старый GUI продолжает работать;
- тесты доказывают atomicity и no-overwrite.

## Этап 3. Локальный backend foundation

### Работы

- Docker Compose: API, PostgreSQL, Redis, worker;
- FastAPI skeleton и `/health`;
- SQLAlchemy models;
- Alembic initial migration;
- local filesystem StorageBackend;
- users and authentication minimum;
- artifacts, logs, revisions, audit models;
- OpenAPI contract.

### Exit criteria

- `docker compose up` запускает весь backend;
- миграции работают на пустой базе;
- backend перезапускается без потери данных;
- тестовый пользователь входит;
- тестовая ревизия принимается через API.

## Этап 4. Desktop offline queue и синхронизация — первый целевой прототип

### Работы

- локальная SQLite queue;
- login/device registration;
- sync manifest;
- idempotency keys;
- upload missing artifacts;
- SHA-256 verification;
- completion receipt;
- retry after interruption;
- conflict creates revision;
- visible queue UI.

### Демонстрационный сценарий

1. Отключить backend.
2. Создать лог в Windows-приложении.
3. Убедиться, что лог в Pending.
4. Запустить backend.
5. Нажать Synchronize.
6. Убедиться, что полный комплект принят.
7. Повторить запрос и доказать отсутствие дубликата.
8. Изменить тот же Log No. и получить новую ревизию.

### Exit criteria

- сценарий проходит автоматически и вручную;
- потеря сети не повреждает очередь;
- серверный receipt сохранён;
- исходные локальные файлы не удалены.

## Этап 5. Минимальный веб-интерфейс поиска

### Работы

- login page;
- ARDOR shell: logo, global search, profile, sidebar, workspace;
- search Log/Pipe/Bundle;
- result table;
- log card;
- revision history;
- preview/download artifacts;
- ZIP download;
- audit display minimum.

### Exit criteria

- синхронизированный Desktop log находится в браузере;
- точный поиск работает по приоритетам;
- все файлы скачиваются и совпадают по SHA-256;
- планшетный layout пригоден для работы.

## Этап 6. Полная обработка CSV в браузере

### Работы

- New Test wizard;
- upload CSV;
- metadata and pipes/bundles;
- photo categories and required validation;
- preview detected columns/unit;
- Celery processing job;
- progress and errors;
- same pressure core;
- Draft/Complete lifecycle.

### Exit criteria

- один CSV обрабатывается из браузера;
- desktop и web дают эквивалентные метрики/artifacts;
- закрытие вкладки не теряет job;
- обязательные фотографии проверяются.

## Этап 7. Роли, ограничения, аудит и confirmation

### Работы

- admin account management;
- должность отдельно от permissions;
- open-by-default visibility;
- selective restrictions;
- temporary passwords/email reset;
- parallel revision branches;
- primary revision selection;
- logical delete/restore;
- confirmation permission;
- confirmed PDF.

### Exit criteria

- правила доступа покрыты integration tests;
- confirmed revision immutable;
- изменения создают новую revision;
- аудит отвечает кто/что/когда;
- удалённое восстанавливается.

## Этап 8. ARDOR Pressure Test Record

### Работы

- record Draft;
- поиск и добавление нескольких логов;
- несколько rows на один лог;
- отдельные производственные поля;
- Test Material;
- validation;
- точный ARDOR PDF;
- preview;
- account confirmation;
- signature image optional;
- upload signed scanned PDF;
- record revision history.

### Exit criteria

- форма визуально совпадает с утверждённым образцом;
- длинные значения и перенос страниц проверены;
- один record поддерживает несколько логов;
- generated, confirmed и scanned PDFs не смешиваются;
- golden PDF test утверждён прорабом.

## Этап 9. Legacy import

### Работы

- inventory old folder;
- TXT parser versions;
- duplicate hashes;
- old/new layout detection;
- dry-run report;
- manual resolution UI/CSV;
- immutable legacy import;
- reconciliation counts.

### Exit criteria

- dry-run ничего не изменяет;
- импорт повторяем и идемпотентен;
- оригинальный архив остаётся нетронутым;
- количества и ошибки документированы.

## Этап 10. UX, локализация и эксплуатационная устойчивость

### Работы

- English/Suomi/Russian;
- accessibility and keyboard navigation;
- notifications;
- performance for 10k logs;
- backup/restore locally;
- structured logs;
- health/readiness;
- dependency/security scan;
- Desktop update checker via GitHub Releases;
- installer upgrade test.

### Exit criteria

- три языка проходят UI smoke tests;
- поиск укладывается в согласованное время;
- backup восстановлен на чистом окружении;
- Desktop upgrade не теряет queue/settings.

## Этап 11. Ubuntu staging

### Предусловия

- все предыдущие локальные exit criteria выполнены;
- есть staging deployment plan;
- известны ресурсы сервера;
- согласованы домен/VPN/HTTPS;
- сделан baseline существующих контейнеров;
- определены отдельные database/volumes/ports.

### Работы

- развернуть отдельный Compose project;
- TLS/reverse proxy;
- staging secrets;
- backup jobs;
- restore drill;
- resource limits;
- smoke/E2E;
- security review.

### Exit criteria

- существующие проекты сервера не изменены;
- staging проходит полный flow;
- backup/restore доказан;
- есть rollback procedure.

## Этап 12. Демонстрация начальству и pilot

### Демонстрация

- Desktop offline processing;
- sync queue;
- browser search;
- revision/audit;
- web CSV processing;
- ARDOR Pressure Test Record;
- confirmation;
- download package;
- recovery after error.

### Результат

- список feedback;
- approved pilot scope;
- выбранные пользователи;
- training materials;
- решение о production.

## Будущие возможности, заложенные архитектурно

Не реализуются заранее, но не должны блокироваться моделью:

- другие шаблоны заказчиков;
- DOCX template adapter;
- batch CSV processing;
- QR/barcode pipe input;
- S3/MinIO storage;
- multiple organizations;
- customer portal;
- certified electronic signature;
- comparison of tests;
- dashboards and statistics;
- mobile-oriented capture;
- API integrations with ERP/document systems;
- retention policies by project;
- configurable engineering criteria;
- automatic document numbering.

## Рекомендуемый первый утверждаемый implementation scope

После утверждения документов начать только с **Этапа 1**. Не создавать backend или сайт до завершения baseline/audit. Первый видимый продуктовый milestone — конец **Этапа 4**, когда Windows-приложение офлайн создаёт лог и безопасно синхронизирует полный комплект в локальный Docker backend.
