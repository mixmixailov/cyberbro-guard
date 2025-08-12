## CyberBro Guard
Telegram-бот (FastAPI + python-telegram-bot 20.7) с вебхуком через внешний HTTPS, хранением в SQLite и минимальными зависимостями.

### 1) Установка
```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 2) Настройка .env
Создай файл `.env` в корне проекта со значениями:
```
BOT_TOKEN=123456:ABC-DEF...
PUBLIC_BASE=
DEBUG=false
```
Примечания:
- BOT_TOKEN — токен бота. В логах он маскируется.
- PUBLIC_BASE — публичный HTTPS базовый URL (без завершающего слэша и без `/webhook`). Локально можно оставить пустым.
- DEBUG=true включает расширенные логи входящих апдейтов.

### 3) Локальный запуск с cloudflared
```bash
make dev
# В другом окне
cloudflared tunnel --url http://localhost:8000
```
Скопируй выданный HTTPS URL вида `https://<random>.trycloudflare.com`.

### 4) Установка вебхука (delete → set → get)
```bash
BOT_TOKEN=<token> make del-webhook
PUBLIC_BASE=https://<random>.trycloudflare.com BOT_TOKEN=<token> make set-webhook
BOT_TOKEN=<token> make get-webhook
```
Ожидаемо: URL в `get-webhook` оканчивается ровно на `/webhook` (без дублей).

### 5) Тесты
- Реальный чат: отправь боту `/start` — ответит «CyberBro Guard на связи.»
- Локальный POST на вебхук без Telegram:
```bash
make ping
```
Ожидаемо: HTTP 200 и `{"ok": true}`; в логах строки вида «Webhook hit» и «Update queued».

### 6) Docker
```bash
docker build -t cyberbro-guard .
docker run --rm -p 8000:8000 --env-file .env cyberbro-guard
```

### 7) Деплой на Railway
1) Подготовка репозитория: запушьте проект в GitHub.
2) В Railway: New Project → Deploy from GitHub → выберите репозиторий.
3) После первого деплоя зайдите в Settings → Variables и добавьте:
   - `BOT_TOKEN=<ваш_токен>`
   - `DEBUG=false`
   - (опционально) `PUBLIC_BASE=https://<your-service>.railway.app`
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

### 7) Makefile команды
- dev — запустить сервер (uvicorn)
- set-webhook — установить вебхук (нужны `PUBLIC_BASE` и `BOT_TOKEN`)
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

## Make команды
- dev: запустить сервер (uvicorn)
- set-webhook: установить вебхук (нужны переменные `PUBLIC_BASE` и `BOT_TOKEN`)
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