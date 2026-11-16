# Events Aggregator

Сервис на **FastAPI** для синхронизации мероприятий из Events Provider, хранения данных в PostgreSQL и регистрации участников. Проект разворачивается в Docker и учебном Kubernetes-кластере LMS.

## Возможности

- Полная первоначальная и последующая инкрементальная синхронизация по `changed_at`.
- Просмотр мероприятий с фильтром по дате и постраничной навигацией.
- Получение доступных мест от Events Provider с локальным кэшем на 30 секунд.
- Регистрация и отмена билетов через провайдера с сохранением записей в PostgreSQL.
- Автоматическая синхронизация при старте и каждые 24 часа (настраивается).

## Стек

Python 3.14, FastAPI, Pydantic Settings, `httpx.AsyncClient`, SQLAlchemy 2.x (`AsyncSession`), psycopg 3, PostgreSQL, Alembic, pytest, Ruff, uv, Docker и GitHub Actions.

## Быстрый запуск через Docker Compose

1. Создайте локальную конфигурацию: `cp .env.example .env`.
2. Установите `LMS_TOKEN` — API-ключ **Events Provider**, передаваемый в заголовке `x-api-key`. Не путайте его с `LMS_API_KEY`, который GitHub Actions использует для отправки деплой-запросов в LMS.
3. Запустите приложение и PostgreSQL:

   ```bash
   docker compose up --build -d
   docker compose ps
   ```

4. Проверьте API:

   ```bash
   curl http://localhost:8000/api/health
   curl -X POST http://localhost:8000/api/sync/trigger
   curl 'http://localhost:8000/api/events?page=1&page_size=20'
   ```

Документация OpenAPI: <http://localhost:8000/docs>. При старте контейнер выполняет `alembic upgrade head`. Для остановки: `docker compose down` (данные БД в Docker volume сохраняются); для удаления данных: `docker compose down -v`.

## Запуск без контейнера приложения

Необходимы Python 3.14, [uv](https://docs.astral.sh/uv/) и работающая PostgreSQL.

```bash
cp .env.example .env
# Установите LMS_TOKEN и при необходимости DATABASE_URL в .env
uv sync --frozen
docker compose up -d db
uv run alembic upgrade head
uv run uvicorn events_aggregator.main:app --reload
```

При запуске напрямую с хоста `DATABASE_URL` из `.env.example` обращается к `localhost:5432`; в Docker Compose `api` подключается к БД по имени сервиса `db`.

## Настройки окружения

| Переменная | Назначение |
| --- | --- |
| `DATABASE_URL` | URL PostgreSQL, например `postgresql+psycopg://events:events@localhost:5432/events` |
| `POSTGRES_CONNECTION_STRING` | Альтернативное имя URL БД, используемое LMS; при наличии `DATABASE_URL` приоритет у него |
| `EVENTS_API_URL` | Базовый адрес Events Provider |
| `LMS_TOKEN` | API-ключ Events Provider, передаваемый как `x-api-key` |
| `ENABLE_BACKGROUND_SYNC` | Включить фоновую синхронизацию (`true`/`false`) |
| `SYNC_INTERVAL_SECONDS` | Интервал синхронизации; по умолчанию `86400` (24 часа) |
| `PROVIDER_TIMEOUT` | Тайм-аут HTTP-запросов к провайдеру в секундах |

В LMS для `EVENTS_API_URL` внутри кластера используйте адрес провайдера, доступный по внутреннему DNS:

```text
http://student-system-events-provider-web.student-system-events-provider.svc:8000
```

Значения секретов не следует добавлять в репозиторий. В Git отслеживается только `.env.example` с примерами.

## HTTP API

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/api/health` | Проверка работоспособности |
| POST | `/api/sync/trigger` | Ручная синхронизация (`409`, если уже выполняется) |
| GET | `/api/events` | Список событий: `date_from`, `page`, `page_size` |
| GET | `/api/events/{event_id}` | Детали события из локальной БД |
| GET | `/api/events/{event_id}/seats` | Свободные места, кэш 30 с |
| POST | `/api/tickets` | Регистрация, ответ `201` и `ticket_id` |
| DELETE | `/api/tickets/{ticket_id}` | Отмена регистрации |

Пример регистрации:

```bash
curl -X POST http://localhost:8000/api/tickets \
  -H 'Content-Type: application/json' \
  -d '{"event_id":"<UUID>","first_name":"Ivan","last_name":"Ivanov","email":"ivan@example.com","seat":"A1"}'
```

Некорректные входные данные возвращают `400` (требование контракта LMS). Бизнес-ошибки описаны отдельными исключениями и преобразуются в HTTP-ответы на уровне FastAPI.

## Устройство проекта

```text
src/events_aggregator/
  main.py             FastAPI, маршруты, обработчики ошибок, lifespan
  config.py           Настройки из переменных окружения
  database.py         Асинхронный engine, фабрика сессий, Depends
  models.py           Таблицы SQLAlchemy
  schemas.py          Pydantic-модели запросов и ответов
  statuses.py         EventStatus и SyncStatus (StrEnum)
  errors.py           Доменные исключения
  events_provider.py  Асинхронный HTTP-клиент и курсорный пагинатор
  repositories.py     Асинхронные операции с БД и upsert
  services.py         Синхронизация, регистрация/отмена, получение мест
  cache.py            Кэш свободных мест с TTL
alembic/                Миграции БД
tests/                  Модульные и API-тесты
```

`httpx.AsyncClient` создаётся один раз при старте приложения и закрывается при остановке. Репозитории используют `AsyncSession`. Фоновая синхронизация запускается через `asyncio`.

## Проверки

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Автотесты проекта не заменяют интеграционную проверку против Events Provider и PostgreSQL учебного кластера.

## CI/CD и развёртывание в LMS

Workflow `.github/workflows/ci.yml` запускается при push в `main` и для pull request:

1. `lint` и `test` выполняются независимо.
2. После успешного завершения обеих проверок `publish` публикует образ `ghcr.io/<owner>/<repo>:<commit-sha>`.
3. После публикации `deploy` отправляет запрос в LMS: `POST https://lms.python-labs.ru/api/deploy-requests`.

Для шага `deploy` в GitHub Actions нужен секрет репозитория `LMS_API_KEY` (ключ API самой LMS, **не** ключ Events Provider). В настройках приложения LMS должны присутствовать строка подключения к PostgreSQL и ключ провайдера. Изменение переменных LMS требует повторного развёртывания.

Приложение рассчитано на **один Uvicorn worker и одну реплику Kubernetes**: кэш и блокировка синхронизации находятся в памяти процесса. Для нескольких реплик понадобятся распределённая блокировка (например, PostgreSQL advisory lock), общие кэш/планировщик и согласованная конфигурация.

## Ограничения и детали реализации

- Курсорный пагинатор постепенно загружает страницы провайдера и проверяет повторение курсора.
- Повторная синхронизация использует дату последнего изменения и `upsert`, чтобы не создавать дубликаты при повторном получении событий за день.
- Перед регистрацией проверяется наличие свободного места, но финальное решение остаётся за провайдером: место могут занять между проверкой и регистрацией.
- После регистрации и отмены кэш мест для события сбрасывается.
- Миграция `0001_initial` создаёт таблицы при первом запуске; редактирование уже применённой миграции не заменяет отдельную новую миграцию для действующих БД.
