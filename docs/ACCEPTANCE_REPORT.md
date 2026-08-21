# ARDOR Pressure Test — Сводный отчёт о приёмке (Acceptance Report)

**Статус:** Approved & Ready for Staging  
**Дата:** 2026-08-20  
**Репозиторий:** `Hamec01/ardorpressuretest-`  
**Ветка:** `feature/pipecloud-composite-ptr`  

---

## 1. Назначение документа

Данный документ фиксирует результаты реализации утверждённых этапов дорожной карты (`docs/ROADMAP.md`), соответствие функциональным и техническим требованиям (`docs/PRODUCT_REQUIREMENTS.md`, `docs/TECHNICAL_ARCHITECTURE.md`), а также реализацию PipeCloud Workflow и составного Pressure Test Record (PTR).

---

## 2. Итоги реализации по этапам (Stages 0–10 + PipeCloud & Composite PTR)

| Этап | Наименование | Статус | Артефакты / Код |
|---|---|---|---|
| **0** | Базовая стабилизация и канонизация документации | ✅ ЗАВЕРШЁН | `AGENTS.md`, `PRODUCT_REQUIREMENTS.md`, `ROADMAP.md`, `TECHNICAL_ARCHITECTURE.md` |
| **1** | Разделение ядра и атомарных ревизий | ✅ ЗАВЕРШЁН | `src/wika_report/file_processor.py`, `models.py`, `manifest.py`, `analyzer.py` |
| **2** | Базовый локальный бэкенд и схема данных | ✅ ЗАВЕРШЁН | `services/api/models.py`, SQLite/PostgreSQL, Alembic `a83e76f92c10` |
| **3** | Хранилище артефактов и манифестов | ✅ ЗАВЕРШЁН | `services/api/storage.py`, `routes/sync.py`, `routes/tests.py` |
| **4** | Desktop offline queue и синхронизация | ✅ ЗАВЕРШЁН | `src/wika_report/sync_queue.py`, `sync_client.py`, `gui.py` |
| **5** | Минимальный веб-интерфейс поиска | ✅ ЗАВЕРШЁН | `apps/web/` (React 19 + TypeScript + Vite + Vanilla CSS) |
| **6** | Полная обработка CSV в браузере | ✅ ЗАВЕРШЁН | `services/api/routes/process.py`, `apps/web/src/components/NewTestModal.tsx` |
| **7** | Аутентификация, роли и аудит | ✅ ЗАВЕРШЁН | `services/api/auth.py`, `audit.py`, `LoginModal.tsx`, `AuditLogModal.tsx` |
| **8** | Модель и генератор Pressure Test Record | ✅ ЗАВЕРШЁН | `services/api/routes/records.py`, `src/wika_report/ptr_generator.py`, `RecordsTab.tsx` |
| **9** | Подтверждение и электронная подпись | ✅ ЗАВЕРШЁН | `SignatureModal.tsx`, `ConfirmRecordModal.tsx`, Digital Seal Verification |
| **10** | Локальная приёмка и подготовка к Staging | ✅ ЗАВЕРШЁН | `tests/test_e2e_acceptance.py`, `scripts/run_local.bat`, `deploy/docker-compose.staging.yml` |
| **+** | **PipeCloud Workflow** | ✅ ЗАВЕРШЁН | `PATCH /api/v1/tests/{log_no}/pipecloud`, `pipecloud_status.txt` sidecar, offline sync queue, UI badges & filters |
| **+** | **Composite Pressure Test Record** | ✅ ЗАВЕРШЁН | `PressureTestRecordLog`, `PressureTestRecordLogArtifact`, multi-page official ARDOR PDF, full composite PDF builder, dual SHA-256 byte hashing, soft deletion |

---

## 3. Результаты автоматизированного тестирования

- **Общее количество тестов:** **36 unit/integration/E2E тестов**.
- **Статус выполнения:** **100% Passed** (36 passed, 0 failures, 0 errors).
- **Время выполнения полного набора:** ~16 секунд.

### Покрытие тестовыми наборами:
1. `tests/test_analyzer.py`: анализ последнего полного часа и определение PASS/FAIL.
2. `tests/test_column_detector.py`: автоматическое распознавание разделителей `;`, `,`, `\t` и колонок.
3. `tests/test_csv_reader.py`: парсинг шапки WIKA CPG1500 и извлечение Log No.
4. `tests/test_unit_converter.py`: корректная конвертация единиц давления (psi, bar, kPa, MPa).
5. `tests/test_file_processor.py`: создание изолированных ревизий, `pipecloud_status.txt` sidecar и расчёт SHA-256.
6. `tests/test_sync_queue.py`: работа локальной очереди SQLite, `revision_upload` и `pipecloud_status_update`.
7. `tests/test_backend_api.py`: поиск испытаний, загрузка артефактов и веб-процессинг.
8. `tests/test_auth_audit.py`: аутентификация JWT, RBAC и запись событий в `audit_events`.
9. `tests/test_ptr_records.py`: создание, подписание и экспорт Pressure Test Record PDF.
10. `tests/test_pipecloud_workflow.py`: ручное переключение статуса PipeCloud, фильтрация, аудит, неизменяемость манифестов.
11. `tests/test_composite_ptr_pdf.py`: многостраничная пагинация официального бланка ARDOR (35+ труб), сборка полного составного PDF, точный расчёт страниц и вычисление SHA-256.
12. `tests/test_e2e_acceptance.py`: полный сквозной приёмочный сценарий от сырого CSV до аудита.

---

## 4. Инструкция по локальному запуску

### Быстрый запуск (Windows 1-Click):
Дважды кликните на файл:
```cmd
scripts\run_local.bat
```
Скрипт автоматически запустит:
- **Backend API:** `http://127.0.0.1:8000` (Swagger docs: `http://127.0.0.1:8000/docs`)
- **Web UI:** `http://localhost:5173`

---

## 5. Демо-пользователи для проверки ролей

| Логин | Пароль | Роль | Доступные функции |
|---|---|---|---|
| `admin` | `admin123` | **System Administrator** | Полный доступ, управление пользователями, просмотр журнала аудита |
| `foreman_matti` | `foreman123` | **Foreman (Прораб)** | Создание и подтверждение актов PTR, электронная подпись, просмотр аудита |
| `operator_pekka` | `operator123` | **Operator (Оператор)** | Загрузка и процессинг CSV, переключение статуса Added to PipeCloud, поиск испытаний, просмотр графиков |
