import json
import os
import sys
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv


def load_env() -> tuple[str | None, str | None]:
    # Загружаем .env из корня проекта вне зависимости от CWD
    project_root = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(project_root, ".env")
    load_dotenv(env_path)
    bot_token = os.getenv("BOT_TOKEN")
    # Compose from PUBLIC_URL + WEBHOOK_PATH if WEBHOOK_URL not provided
    webhook_url = os.getenv("WEBHOOK_URL")
    return bot_token, webhook_url


def api_call(token: str, method: str, params: dict | None = None) -> dict:
    base = f"https://api.telegram.org/bot{token}/{method}"
    if params is None:
        params = {}
    response = requests.post(base, data=params, timeout=15)
    response.raise_for_status()
    return response.json()


def _compose_url(raw: str | None) -> str:
    public_url = os.getenv("PUBLIC_URL")
    webhook_path = os.getenv("WEBHOOK_PATH", "/webhook")
    if raw:
        url = raw.rstrip("/")
    elif public_url:
        url = public_url.rstrip("/") + webhook_path
    else:
        raise SystemExit("Provide WEBHOOK_URL or PUBLIC_URL in environment/.env")
    if not url.endswith("/webhook"):
        raise SystemExit(f"WEBHOOK_URL must end with /webhook, got: {url}")
    return url


def cmd_set(token: str, webhook_url: str | None) -> None:
    url = _compose_url(webhook_url)
    payload = {"url": url, "drop_pending_updates": True}
    # Optional secret token support if WEBHOOK_SECRET is set
    secret = os.getenv("WEBHOOK_SECRET")
    if secret:
        payload["secret_token"] = secret
    data = api_call(token, "setWebhook", payload)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    # Verify set result by reading back info
    info = api_call(token, "getWebhookInfo")
    current_url = ((info or {}).get("result") or {}).get("url")
    if current_url != url:
        print(f"WARNING: getWebhookInfo.url != expected url\n expected={url}\n actual={current_url}")


def cmd_get(token: str) -> None:
    data = api_call(token, "getWebhookInfo")
    result = data.get("result", {}) if isinstance(data, dict) else {}
    pretty = {
        "url": result.get("url"),
        "pending_update_count": result.get("pending_update_count"),
        "last_error_date": result.get("last_error_date"),
        "last_error_message": result.get("last_error_message"),
    }
    print(json.dumps(pretty, indent=2, ensure_ascii=False))


def cmd_delete(token: str) -> None:
    payload = {"drop_pending_updates": True}
    data = api_call(token, "deleteWebhook", payload)
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in {"set", "get", "delete"}:
        print("Usage: python manage_webhook.py [set|get|delete]")
        sys.exit(2)

    action = sys.argv[1]
    bot_token, webhook_url = load_env()
    if not bot_token:
        print("BOT_TOKEN is missing in environment/.env", file=sys.stderr)
        sys.exit(1)

    if action == "set":
        cmd_set(bot_token, webhook_url)
    elif action == "get":
        cmd_get(bot_token)
    elif action == "delete":
        cmd_delete(bot_token)


if __name__ == "__main__":
    main()



