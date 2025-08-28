# CyberBro Guard: Репозиторный аудит

**Дата аудита:** Январь 2025  
**Версия:** Commit HEAD  
**Аудитор:** AI Assistant  

## Общие сведения

CyberBro Guard — Telegram-бот для модерации групп с использованием aiogram 3.x + FastAPI webhook, SQLite+forward-only миграции, i18n, платежи Telegram Stars, анти-спам middleware, опциональная AI-модерация.

**Ключевые технологии:**
- Python 3.11+, python-telegram-bot v21+, FastAPI, uvicorn
- SQLite с WAL mode, forward-only миграции
- Telegram Stars платежи (XTR)
- Docker + Railway/Render деплой
- Prometheus метрики, структурированные логи

---

## 1. Структура & архитектура

### ✅ Found
- **Модульная архитектура**: `app/{handlers/, services/, db/, middleware/, utils/}`
- **Чистое разделение слоёв**: handlers → services → db
- **DI через Application.bot_data**: SendQueue, настройки
- **Никаких глобальных переменных состояния**: всё через context
- **Pydantic конфигурация**: BaseSettings с валидацией
- **Корректная структура PTB**: handlers → services → database

### ⚠️ Risks
- **Отсутствует явный интерфейс/protocol** для сервисов
- **Сервисы импортируют друг друга** напрямую без инверсии зависимостей
- **app/bot.py практически пустой** — основная логика в main.py

### 🔧 Fix Plan (diff-friendly)
```python
# app/services/protocols.py
from abc import ABC, abstractmethod

class ModerationServiceProtocol(ABC):
    @abstractmethod
    async def moderate_message(self, text: str) -> bool: ...

# app/services/__init__.py  
# Добавить registry pattern для сервисов
```

---

## 2. Безопасность

### ✅ Found
- **Webhook secret проверка**: X-Telegram-Bot-Api-Secret-Token header
- **Все секреты через env**: BOT_TOKEN, WEBHOOK_SECRET, OPENAI_API_KEY
- **Константные сравнения**: hmac.compare_digest в verify_secret
- **Размер payload ограничен**: MAX_WEBHOOK_BODY (1MB по умолчанию)  
- **Content-Type проверка**: только application/json
- **Rate limiting**: TokenBucket с cooldown

### ⚠️ Risks
- **Пустой WEBHOOK_SECRET по умолчанию** → только warning в логах
- **Отсутствует CSRF защита** для админских эндпоинтов
- **Логирование может содержать PII** (user IDs в clear text)

### 🔧 Fix Plan (diff-friendly)
```python
# app/config.py
@field_validator("WEBHOOK_SECRET")
def _validate_webhook_secret(cls, v: str) -> str:
    if not v.strip() and not cls.DEBUG:
        raise ValueError("WEBHOOK_SECRET required in production")
    return v

# app/main.py - добавить CSRF middleware для admin routes
from starlette.middleware.trustedhost import TrustedHostMiddleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*.railway.app", "localhost"])
```

---

## 3. SQLite надёжность

### ✅ Found
- **WAL mode включён**: `PRAGMA journal_mode=WAL`
- **Безопасный timeout**: `PRAGMA busy_timeout=5000`
- **Foreign keys включены**: `PRAGMA foreign_keys=ON`
- **Транзакционные операции**: context managers с commit/rollback
- **Connection pooling через _get_conn()**: изоляция соединений

### ⚠️ Risks
- **Отсутствует BEGIN IMMEDIATE** для критических операций
- **Нет явных checkpoint операций** для WAL
- **Отсутствует мониторинг размера WAL** файла
- **check_same_thread=False без thread safety** гарантий

### 🔧 Fix Plan (diff-friendly)
```python
# app/db/session.py
def _get_conn(immediate: bool = False) -> sqlite3.Connection:
    conn = sqlite3.connect(APP_DB_PATH, timeout=30, check_same_thread=False)
    # ... existing pragma setup ...
    if immediate:
        conn.execute("BEGIN IMMEDIATE")
    return conn

# Добавить WAL checkpoint в scheduler
def wal_checkpoint() -> None:
    with _get_conn() as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
```

---

## 4. Forward-only миграции

### ✅ Found
- **Простой мигратор**: app/utils/migrate.py
- **Версионирование**: schema_version таблица
- **Forward-only**: только .sql файлы с номерами
- **Транзакционность**: BEGIN/COMMIT для каждой миграции
- **Нет downgrade**: только forward применение

### ⚠️ Risks
- **Отсутствует render_as_batch** для SQLite ALTER TABLE
- **Нет dry-run режима** для production проверки  
- **Отсутствует бэкап** перед миграцией
- **Нет валидации SQL** перед применением

### 🔧 Fix Plan (diff-friendly)
```python
# app/utils/migrate.py
def _backup_db() -> str:
    timestamp = int(time.time())
    backup_path = f"{APP_DB_PATH}.backup.{timestamp}"
    shutil.copy2(APP_DB_PATH, backup_path)
    return backup_path

def migrate(migrations_dir: str, dry_run: bool = False, backup: bool = True) -> int:
    if backup and not dry_run:
        backup_path = _backup_db()
        logger.info("Database backed up to %s", backup_path)
    # ... rest of function
```

---

## 5. Платежи Telegram Stars

### ✅ Found
- **XTR валюта**: правильные LabeledPrice для Stars  
- **Idempotency на charge_id**: предотвращение дублирования
- **SuccessfulPayment обработка**: record_payment + upsert_subscription
- **Refund поддержка**: refund_star_payment с временным окном
- **Audit trail**: payment_audit таблица для отслеживания действий
- **Retry механизм**: 3 попытки для sendInvoice

### ⚠️ Risks
- **Отсутствует StarTransaction обработка** (новые типы webhook)
- **RefundedPayment events не обрабатываются**
- **Нет проверки подписи webhook** от Telegram для платежей
- **Race condition** в seen_charge_id проверке

### 🔧 Fix Plan (diff-friendly)
```python
# app/handlers/payments.py
async def handle_star_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle star_transaction updates for enhanced payment tracking"""
    if not update.star_transaction:
        return
    # ... implement StarTransaction logic

# app/db/payments.py  
def seen_charge_id(charge_id: str) -> bool:
    # Add UNIQUE constraint + INSERT OR IGNORE for atomicity
    with _get_conn() as conn:
        try:
            conn.execute("INSERT INTO seen_charges (charge_id) VALUES (?)", (charge_id,))
            return False  # Not seen before
        except sqlite3.IntegrityError:
            return True   # Already seen
```

---

## 6. Анти-спам & 429 backoff

### ✅ Found
- **TokenBucket rate limiting**: настраиваемые rate/burst/cooldown
- **Per-user + per-chat scopes**: гибкое ограничение
- **RetryAfter обработка**: в SendQueue с динамическим ожиданием
- **Prometheus метрики**: cyberbro_abuse_rate_limit_total
- **Cleanup job**: автоматическая очистка старых токенов

### ⚠️ Risks
- **Отсутствует jitter** в backoff алгоритме
- **Нет адаптивного rate limiting** под нагрузкой  
- **Rate limits хранятся в памяти** — сбрасываются при рестарте
- **429 от Telegram API не всегда содержит retry_after**

### 🔧 Fix Plan (diff-friendly)
```python
# app/services/send_queue.py
import random

async def _send(self, item: _Item) -> None:
    # ... existing code ...
    except RetryAfter as e:
        # Add jitter to avoid thundering herd
        retry_time = float(getattr(e, "retry_after", 1.0)) or 1.0
        jitter = random.uniform(0.1, 0.3) * retry_time
        await asyncio.sleep(retry_time + jitter)

# app/services/rate_limit.py - persist to SQLite
class PersistentTokenBucket(TokenBucket):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._load_from_db()
    
    def _save_to_db(self): ...
```

---

## 7. Queue worker

### ✅ Found
- **Background worker task**: asyncio.Queue для webhook updates
- **Timeout handling**: asyncio.timeout для process_update
- **Error isolation**: каждый update обрабатывается изолированно
- **Graceful shutdown**: task.cancel() в lifespan cleanup
- **Idempotency layer**: IdempotencyStore для дедупликации

### ⚠️ Risks
- **Отсутствует dead letter queue** для failed updates
- **Нет retry механизма** с экспоненциальным backoff  
- **Queue overflow не обрабатывается** (maxsize=1000)
- **State machine отсутствует**: PENDING→PROCESSING→FINISHED/ERROR

### 🔧 Fix Plan (diff-friendly)
```python
# app/services/update_processor.py
from enum import Enum

class UpdateStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"  
    FINISHED = "finished"
    ERROR = "error"

class UpdateProcessor:
    def __init__(self):
        self._queue = asyncio.Queue(maxsize=1000)
        self._dead_letter = asyncio.Queue(maxsize=500)
        
    async def _worker(self):
        while True:
            try:
                update = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._process_with_retries(update)
            except asyncio.TimeoutError:
                continue  # Check shutdown
```

---

## 8. CI/CD

### ✅ Found
- **Docker multi-stage build**: builder + runner stages  
- **Health checks**: curl-based в docker-compose.yml
- **Non-root user**: security best practices
- **Requirements с hash validation**: pip-compile generated
- **Local development scripts**: Makefile, start_local.ps1/.sh

### ⚠️ Risks
- **Отсутствуют GitHub Actions** (нет .github/workflows/)
- **Нет matrix testing** Python 3.11/3.13
- **Отсутствует pip cache** в CI  
- **Нет автоматических тестов** в CI pipeline
- **Отсутствуют build artifacts** сохранение

### 🔧 Fix Plan (diff-friendly)
```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]
jobs:
  test:
    strategy:
      matrix:
        python-version: ["3.11", "3.13"]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: ruff check .
      - run: pytest tests/ -v
      - uses: actions/upload-artifact@v4
        with:
          name: test-results-${{ matrix.python-version }}
          path: reports/
```

---

## 9. MCP конфигурация

### ✅ Found
- **Context7 упоминание**: в project rules про MCP usage
- **E2E тесты**: tests/ директория с webhook/payments тестами
- **Playwright готовность**: упоминание в constraints

### ⚠️ Risks  
- **Отсутствует .cursor/mcp.json** конфигурация
- **Нет playwright-mcp** интеграции
- **E2E coverage неполный**: нет UI тестирования mini-apps
- **MCP servers не настроены**: context7, brave-search

### 🔧 Fix Plan (diff-friendly)
```json
// .cursor/mcp.json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["@context7/mcp-server"]
    },
    "playwright": {
      "command": "npx", 
      "args": ["@playwright/mcp-server"]
    }
  }
}
```

---

## 10. Интернационализация

### ✅ Found
- **YAML файлы ресурсов**: i18n/ru.yml, i18n/en.yml
- **Lazy loading**: @lru_cache для каталогов  
- **Fallback chain**: выбранный язык → DEFAULT_LOCALE → en → key
- **Formatting поддержка**: .format(**kwargs) в t() функции
- **Language middleware**: через utils.lang.t()

### ⚠️ Risks
- **Нет автоматического language detection** из Telegram user
- **Отсутствует pluralization** (1 item vs 2 items)
- **Hardcoded strings** в некоторых местах кода
- **Нет валидации** отсутствующих ключей в build time

### 🔧 Fix Plan (diff-friendly)
```python
# app/utils/lang.py  
def get_user_language(user) -> str:
    """Extract language from Telegram user with fallback"""
    if user and hasattr(user, 'language_code'):
        return user.language_code[:2].lower() if user.language_code else 'en'
    return get_settings().DEFAULT_LOCALE

# tests/test_i18n_keys.py
def test_all_i18n_keys_present():
    """Validate all i18n keys exist in all locales"""
    catalogs = _load_catalogs()
    base_keys = set(catalogs.get('en', {}).keys())
    for lang, catalog in catalogs.items():
        missing = base_keys - set(catalog.keys())
        assert not missing, f"Missing keys in {lang}: {missing}"
```

---

## TODO Board (Приоритеты)

### P1 (Критичные)
1. **Добавить GitHub Actions CI/CD** с matrix Python 3.11/3.13
2. **Исправить WEBHOOK_SECRET validation** в production режиме  
3. **Реализовать BEGIN IMMEDIATE** для критических транзакций
4. **Добавить StarTransaction/RefundedPayment** обработку
5. **Настроить MCP servers** (.cursor/mcp.json) для context7/playwright

### P2 (Важные)  
6. **Добавить jitter в retry backoff** алгоритмы
7. **Реализовать dead letter queue** для failed updates  
8. **Добавить WAL checkpoint** в scheduler jobs
9. **Улучшить E2E coverage** с playwright mini-app тестами
10. **Добавить database backup** перед миграциями

### P3 (Желательные)
11. **Добавить persistent rate limiting** (SQLite backed)
12. **Реализовать service protocols/interfaces** для DI
13. **Добавить automatic language detection** из Telegram  
14. **Улучшить логирование** (убрать PII, добавить structured fields)
15. **Добавить CSRF protection** для admin endpoints

---

## Заключение

**Общая оценка:** 🟢 **ХОРОШО**

CyberBro Guard демонстрирует качественную архитектуру с правильным разделением слоёв, надёжную работу с SQLite, корректную реализацию Telegram Stars платежей и хорошую базу для production deployment. 

**Ключевые сильные стороны:**
- Чистая модульная архитектура
- Надёжная SQLite конфигурация с WAL  
- Корректная идемпотентность операций
- Хорошее покрытие тестами критических компонентов

**Главные области для улучшения:**
- CI/CD pipeline (отсутствует)
- MCP интеграция для development workflow
- Enhanced error handling с retry mechanisms
- Security hardening (CSRF, webhook validation)

**Рекомендация:** Готов к production после исправления P1 задач.



