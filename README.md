## CyberBro Guard

[![CI](https://github.com/cyberbro-guard/cyberbro-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/cyberbro-guard/cyberbro-guard/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/cyberbro-guard/cyberbro-guard/branch/main/graph/badge.svg)](https://codecov.io/gh/cyberbro-guard/cyberbro-guard)
[![Security](https://img.shields.io/badge/security-trivy%20%2B%20bandit-blue)](https://github.com/cyberbro-guard/cyberbro-guard/security)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.13-blue)](https://github.com/cyberbro-guard/cyberbro-guard/blob/main/.github/workflows/ci.yml)

Telegram-бот (FastAPI + python-telegram-bot 20.7) с вебхуком через внешний HTTPS, хранением в SQLite и минимальными зависимостями.

### Архитектура (вкратце)
- Handlers → Services → DB, без бизнес-логики в хендлерах
- FastAPI принимает вебхук, PTB обрабатывает апдейты, сервисы реализуют модерацию и платежи
- Подробно см. `docs/architecture.md`

### 1) Установка
```bash
py -3.11 -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

#### 1.1) Windows быстрый старт (целевой Python 3.11; совместим с 3.13)
```powershell
./scripts/run_local.ps1
```
Ожидаемо: сервер слушает `http://127.0.0.1:8000` (порт регулируется `PORT` в `.env`).

Fallback без вебхука (polling) — для локальной отладки хендлеров:
```powershell
$env:USE_POLLING="true"; ./scripts/run_local.ps1
```

### 2) Настройка .env
Создай файл `.env` в корне проекта со значениями:
```
BOT_TOKEN=
PUBLIC_BASE=
DEBUG=false
WEBHOOK_SECRET=superlongrandom
CALLBACK_TTL_S=600
ADMIN_IDS=123456789,987654321
DEFAULT_LOCALE=ru
# Stars (XTR)
PAYMENTS_STARS_ENABLED=true
PAYMENTS_STARS_TEST=true
PRO_PRICE_XTR=4900
PRO_PERIOD_DAYS=30
# AI-модерация (опционально)
AI_MODERATION_ENABLED=false
AI_MODERATION_PROVIDER=openai
OPENAI_API_KEY=
AI_MODERATION_ACTION_ON_FLAG=block
AI_MODERATION_APPLIES_TO=inbound
AI_MODERATION_FAIL_OPEN=true
```
Примечания:
- BOT_TOKEN — токен бота. В логах он маскируется.
- Для локального мок‑запуска без Telegram можно оставить `BOT_TOKEN=` пустым при `DEBUG=true`. В продакшене пустой токен недопустим.
- PUBLIC_BASE — публичный HTTPS базовый URL (без завершающего слэша и без `/webhook`). Локально можно оставить пустым.
- DEBUG=true включает расширенные логи входящих апдейтов.

### Environments
- Целевой Python: 3.11 (dev и прод). Проект совместим до Python 3.13, но нельзя использовать 3.13‑only API.
- На Windows используйте запуск через `py -3.11` (см. выше). Примеры в скриптах учитывают это.

### Dependencies (pip‑tools)
- Управляем зависимостями через `pip-tools`: редактируйте `requirements.in`, затем
```powershell
pip-compile --upgrade --generate-hashes --output-file requirements.txt requirements.in -c constraints.txt
pip-sync requirements.txt requirements-dev.txt
```
- `constraints.txt` хранит пины для проблемных пакетов (например, `tiktoken`), чтобы не ломалось на Python 3.13.

### SQLite best practices
- Включён WAL: `PRAGMA journal_mode=WAL`.
- Таймаут ожидания блокировок: `PRAGMA busy_timeout`.
- Избегайте апгрейда read‑транзакций в write; иначе возможен `SQLITE_BUSY` на Windows.

### Webhook security
- Обязательна проверка заголовка `X-Telegram-Bot-Api-Secret-Token` в `/webhook`.
- Установка вебхука с секретом:
```powershell
$env:BOT_TOKEN="<token>"; $env:PUBLIC_URL="https://<domain>"; $env:WEBHOOK_SECRET="<secret>"; python manage_webhook.py delete; python manage_webhook.py set; python manage_webhook.py info
```

### Optional features
- Пакеты без колёс под 3.13 (например, `tiktoken`) подключайте опционально, через extras/флаги. Импортируйте их только при явном включении фичи.

### CI/Test matrix
- Тесты должны проходить на Python 3.11 и 3.13.
- Деплой осуществляется на Python 3.11.

### 3) Локальный запуск с cloudflared
```bash
make dev
# В другом окне
cloudflared tunnel --url http://localhost:8000
```
Скопируй выданный HTTPS URL вида `https://<random>.trycloudflare.com`.

#### 3.1) Локальный запуск на Windows (без Docker)
```powershell
./scripts/run_local.ps1
# В другом окне (если нужен внешний вебхук)
cloudflared tunnel --url http://localhost:8000
```

### 4) Установка вебхука (delete → set → get)
```bash
BOT_TOKEN=<token> make del-webhook
PUBLIC_BASE=https://<random>.trycloudflare.com WEBHOOK_SECRET=<secret> BOT_TOKEN=<token> make set-webhook
BOT_TOKEN=<token> make get-webhook
```
Ожидаемо: URL в `get-webhook` оканчивается ровно на `/webhook` (без дублей).

Рекомендуемая новая схема переменных:
- `PUBLIC_URL` — публичный базовый URL (например, `https://<random>.trycloudflare.com`)
- `WEBHOOK_PATH` — путь вебхука (по умолчанию `/webhook`)

PowerShell (рекомендуется):
```powershell
$env:BOT_TOKEN="<token>"
$env:PUBLIC_URL="https://<random>.trycloudflare.com"
$env:WEBHOOK_SECRET="<secret>"
python manage_webhook.py delete
python manage_webhook.py set
python manage_webhook.py info
```
Проверка вручную, что маршрут существует:
```bash
curl -i https://<random>.trycloudflare.com/webhook
# ожидаемо: 405/415 (метод/контент), но не 404
```

### Админ‑панель (минимум)
Требуется токен в окружении: `ADMIN_PANEL_TOKEN`.

Проверка статуса и переключение флагов:
```powershell
$env:ADMIN_PANEL_TOKEN="<admin_token>"
curl.exe -H "X-Admin-Token: $env:ADMIN_PANEL_TOKEN" http://127.0.0.1:8000/admin/status | cat
curl.exe -X POST -H "X-Admin-Token: $env:ADMIN_PANEL_TOKEN" -H "Content-Type: application/json" -d '{"AI_MODERATION_ENABLED":true,"USE_POLLING":false}' http://127.0.0.1:8000/admin/toggles | cat
```

Windows (PowerShell) one-liners:
```powershell
$env:BOT_TOKEN="<token>"; python scripts/manage_webhook.py delete
$env:PUBLIC_BASE="https://<random>.trycloudflare.com"; $env:WEBHOOK_SECRET="<secret>"; $env:BOT_TOKEN="<token>"; python scripts/manage_webhook.py set
$env:BOT_TOKEN="<token>"; python scripts/manage_webhook.py get
```

### 5) Тесты
- Реальный чат: отправь боту `/start` — ответит «CyberBro Guard на связи.»
- Локальный POST на вебхук без Telegram:
```bash
make ping
```
Ожидаемо: HTTP 200 и `{"ok": true}`; в логах строки вида «Webhook hit» и «Update queued».

PowerShell self-check:
```powershell
curl.exe http://127.0.0.1:8000/healthz
curl.exe http://127.0.0.1:8000/status
python scripts/ping_webhook.py
```

Метрики Prometheus на `/metrics`:
- `cyberbro_updates_total{type,chat_type}` — входящие апдейты
- `cyberbro_webhook_dropped_total{reason}` — отфильтрованные/дубликаты/слишком большие
- `cyberbro_webhook_errors_total{stage}` — ошибки на /webhook
- `cyberbro_payments_total{status}` — попытки платежей (ok/failed_api)

### 6) Docker
```bash
docker build -t cyberbro-guard .
```

Контейнер слушает порт `8080` внутри. Примеры запуска:

Linux/macOS (Bash):
```bash
docker run --rm -p 8080:8080 --env-file .env \
  -e PORT=8080 -e BOT_TOKEN="$BOT_TOKEN" -e WEBHOOK_SECRET="$WEBHOOK_SECRET" \
  cyberbro-guard
```

Windows PowerShell:
```powershell
docker run --rm -p 8080:8080 --env-file .env `
  -e PORT=8080 -e BOT_TOKEN=$env:BOT_TOKEN -e WEBHOOK_SECRET=$env:WEBHOOK_SECRET `
  cyberbro-guard
```
В образе включён HEALTHCHECK на `/readyz` (curl).

### 6.1) Быстрый старт (docker-compose)
- Linux/macOS (Bash):
```bash
./scripts/start_local.sh
# с туннелем cloudflared
PROFILE=tunnel ./scripts/start_local.sh
# с ngrok (нужен $NGROK_AUTHTOKEN)
PROFILE=tunnel_ngrok ./scripts/start_local.sh
```

- Windows PowerShell:
```powershell
./scripts/start_local.ps1
# с туннелем cloudflared
$env:PROFILE="tunnel"; ./scripts/start_local.ps1
# с ngrok (нужен $env:NGROK_AUTHTOKEN)
$env:PROFILE="tunnel_ngrok"; ./scripts/start_local.ps1
```

После старта проверьте `http://localhost:8080/healthz`. URL туннеля будет в логах контейнера `cloudflared` или `ngrok`.

### 6.2) Установка вебхука
1) Получите публичный URL (напр., из туннеля): `https://<random>.trycloudflare.com`
2) Установите:
   - Bash:
```bash
WEBHOOK_URL=https://<random>.trycloudflare.com ./scripts/start_local.sh
```
   - PowerShell:
```powershell
$env:WEBHOOK_URL="https://<random>.trycloudflare.com"; ./scripts/start_local.ps1
```

### 7) Деплой на Railway
1) Подготовка репозитория: запушьте проект в GitHub.
2) В Railway: New Project → Deploy from GitHub → выберите репозиторий.
3) После первого деплоя зайдите в Settings → Variables и добавьте:
   - `BOT_TOKEN=<ваш_токен>`
   - `DEBUG=false`
   - (опционально) `PUBLIC_BASE=https://<your-service>.railway.app`
   - В проде сервис слушает порт из переменной `PORT`, задаётся платформой автоматически.
4) Если `PUBLIC_BASE` не задан, установите вебхук вручную с помощью скрипта (локально):
```bash
BOT_TOKEN=<token> PUBLIC_BASE=https://<your-service>.railway.app python scripts/manage_webhook.py set
```
5) Проверьте здоровье и статус:
```bash
curl https://<your-service>.railway.app/healthz
curl https://<your-service>.railway.app/status
curl https://<your-service>.railway.app/tg_webhook_info
```
Ожидаемо: 200 на /healthz, в /status `running: true`, и в `tg_webhook_info` URL, оканчивающийся ровно на `/webhook`.

### 9) Платежи Stars (XTR)
- Включите `PAYMENTS_STARS_ENABLED=true` и при тесте `PAYMENTS_STARS_TEST=true`.
- Команды: `/plan`, `/buy_pro` (инвойс XTR), оплата → PRO на `PRO_PERIOD_DAYS`.
- Идемпотентность по `telegram_payment_charge_id`.
- Напоминания T-3/T-1/T0 на продление (опциональный фон-джоб).
 - Месячная квота AI на чат: `AI_MONTHLY_QUOTA` (по умолчанию 20k проверок/мес). В `/plan` в группе показывается usage.

### 10) Security checklist
- WEBHOOK_SECRET установлен; /webhook проверяет секрет и лимит тела `MAX_WEBHOOK_BODY`.
- ALLOWED_UPDATES не пустой: задайте в .env или через `--allowed`.
- Логи в JSON без PII (маскирование токенов/e‑mail/телефонов), есть request_id и update_context.
- База в `data/app.db`; делайте бэкапы и ограничьте доступ.

### 11) Runbook (инциденты)
- Бот не отвечает: проверьте `/readyz`, `/status`, `scripts/manage_webhook.py --info` (URL и pending_update_count).
- Дубликаты апдейтов: посмотрите idempotency (update_id) и pending в webhook info.
- Платеж не активировал PRO: проверьте `payments`, повторите `/buy_pro`, посмотрите логи `successful_payment`.
- Возврат: `/refund_last` в личке; тикет создастся автоматически.

### 12) CI/CD
- CI: ruff, black --check, mypy --strict, pytest с coverage, docker build/push.
- Бейдж см. сверху. Workflow в `.github/workflows/ci.yml`.

### 13) Обновления
- Поддерживается секрет вебхука в заголовке `X-Telegram-Bot-Api-Secret-Token` (актуально по Bot API).
- Платежи Stars включаются флагом `PAYMENTS_STARS_ENABLED=true`; при `false` команды оплаты недоступны.
- Refund соблюдает окно `REFUND_WINDOW_H` при наличии времени платежа в payload.
- Редактирование allowlist ссылок: команда `/settings` → кнопка Allowlist → отправьте список доменов через запятую.

### 7) Makefile команды
- dev — запустить сервер (uvicorn)
- set-webhook — установить вебхук (нужны `PUBLIC_BASE`, `BOT_TOKEN`, опционально `WEBHOOK_SECRET`)
- get-webhook — получить текущее значение вебхука (нужен `BOT_TOKEN`)
- del-webhook — удалить вебхук (нужен `BOT_TOKEN`)
- ping — отправить sample-апдейт в вебхук

Примеры:
```bash
make dev
PUBLIC_BASE=https://<random>.trycloudflare.com BOT_TOKEN=<token> make set-webhook
BOT_TOKEN=<token> make get-webhook
BOT_TOKEN=<token> make del-webhook
make ping
```

### 8) Важное
- Не коммить `.env`. При утечке — ротируй `BOT_TOKEN` в BotFather и обнови вебхук.
- Эндпоинты проверки: `/healthz`, `/status`, `/db_health`, `/tg_webhook_info`.
 - Privacy: `/privacy` — краткая политика сбора и хранения (без PII, маскирование токенов, счётчики AI).

## Make команды
- dev: запустить сервер (uvicorn)
- set-webhook: установить вебхук (нужны переменные `PUBLIC_BASE`, `BOT_TOKEN`, опционально `WEBHOOK_SECRET`)
- get-webhook: получить текущее значение вебхука (нужен `BOT_TOKEN`)
- del-webhook: удалить вебхук (нужен `BOT_TOKEN`)
- ping: отправить sample-апдейт на локальный вебхук

Примеры:
```bash
make dev
PUBLIC_BASE=https://<random>.trycloudflare.com BOT_TOKEN=<token> make set-webhook
BOT_TOKEN=<token> make get-webhook
BOT_TOKEN=<token> make del-webhook
make ping
```