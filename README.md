# CyberBro Guard (MVP)
Telegram админ-бот: фильтрация токсиков/спама, вебхук на FastAPI, SQLite, Docker.

## Требования
- Python 3.11+
- Установленные зависимости из `requirements.txt`

## Подготовка окружения
1) Создай файл `.env` в корне проекта (или скопируй из `.env.sample`) и укажи:
```
BOT_TOKEN=123456:ABC-DEF...
WEBHOOK_URL=https://your.domain.tld/telegram  # можно оставить пустым локально
PORT=8000
ENV=dev
TZ=UTC
```

2) Установи зависимости и очисти конфликтующие пакеты:
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# На всякий случай удалим конфликтующие пакеты и зафиксируем PTB 20.7
pip uninstall -y telegram || true
pip uninstall -y python-telegram-bot || true
pip install python-telegram-bot==20.7
```

## Локальный запуск
```bash
make dev
```
Ожидаемые логи на старте:
```
Config snapshot: BOT_TOKEN=***SET***, PUBLIC_BASE=True|False, DEBUG=False
PTB Application started
```
Если задан `PUBLIC_BASE`, будет лог:
```
Webhook set to https://...
```

Проверка здоровья:
```bash
curl http://127.0.0.1:8000/healthz
```

## Проверка токена отдельно
```bash
python test_token.py
```
Ожидаемо: в логах информация о боте (`id`, `username`).

## Docker (опционально)
```bash
docker build -t cyberbro-guard .
docker run --rm -p 8000:8000 --env-file .env cyberbro-guard
```

## Замечания
- Никогда не логируем BOT_TOKEN в открытом виде — в логах только индикатор `***SET***`.
- Проект работает через вебхуки. Long polling не используется.

## Локальный запуск с вебхуком
1) Старт приложения:
```bash
make dev
```
2) Поднять Cloudflared и получить HTTPS URL:
```bash
cloudflared tunnel --url http://localhost:8000
```
3) Прописать webhook:
```bash
PUBLIC_BASE=https://<random>.trycloudflare.com BOT_TOKEN=<token> make set-webhook
```
4) В Telegram отправить боту `/start`.

5) Проверить логи: должен быть INFO `/webhook: received update type=message user_id=<id>`.

Проверки:
- GET /healthz → ok
- GET /status → JSON с полями `webhook`, `running`, `config.public_base`, `config.debug`

## Локальный тест вебхука без Telegram
1) Запусти сервер:
```bash
make dev
```
2) Отправь sample-апдейт:
```bash
python scripts/ping_webhook.py
```
Ожидаемо: HTTP 200 и `{"ok": true}`. В логах — запись о получении update и user_id.

## Диагностика вебхука
- Проверить текущий вебхук в Telegram:
```bash
curl http://127.0.0.1:8000/tg_webhook_info
```
- Локальный пинг вебхука:
```bash
PUBLIC_BASE=http://127.0.0.1:8000 python scripts/ping_webhook.py
```
- Типичные ошибки:
  - Дублированный путь (например, PUBLIC_BASE уже содержит `/webhook`). Решение: указывать только базовый URL без `/webhook`.
  - Неверный PUBLIC_BASE (без HTTPS для реального Telegram). Решение: использовать cloudflared/ngrok HTTPS URL.
  - secret_token: если вы включите секреты для вебхука — убедитесь, что задаёте их одинаково в `set_webhook` и проверяете в бекенде.

Траблшутинг:
- 401 от Telegram: проверь токен — `python test_token.py` (должен вывести username)
