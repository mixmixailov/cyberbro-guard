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
    webhook_url = os.getenv("WEBHOOK_URL")
    return bot_token, webhook_url


def api_call(token: str, method: str, params: dict | None = None) -> dict:
    base = f"https://api.telegram.org/bot{token}/{method}"
    if params is None:
        params = {}
    response = requests.post(base, data=params, timeout=15)
    response.raise_for_status()
    return response.json()


def cmd_set(token: str, webhook_url: str) -> None:
    url = webhook_url.rstrip("/") + "/webhook"
    payload = {"url": url, "drop_pending_updates": True}
    data = api_call(token, "setWebhook", payload)
    print(json.dumps(data, indent=2, ensure_ascii=False))


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
        if not webhook_url:
            print("WEBHOOK_URL is missing in environment/.env", file=sys.stderr)
            sys.exit(1)
        cmd_set(bot_token, webhook_url)
    elif action == "get":
        cmd_get(bot_token)
    elif action == "delete":
        cmd_delete(bot_token)


if __name__ == "__main__":
    main()



