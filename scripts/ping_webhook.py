import json
import os
import sys
from pathlib import Path

import requests


DEFAULT_SAMPLE = {
    "update_id": 999999999,
    "message": {
        "message_id": 1,
        "date": 1710000000,
        "chat": {"id": 123456789, "type": "private"},
        "from": {"id": 123456789, "is_bot": False, "first_name": "Test"},
        "text": "/start",
    },
}


def main() -> None:
    # Determine sample path
    sample_path = Path("samples/update_message.json")
    if not sample_path.exists():
        sample_path.parent.mkdir(parents=True, exist_ok=True)
        sample_path.write_text(json.dumps(DEFAULT_SAMPLE, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Created sample: {sample_path}")

    data = json.loads(sample_path.read_text(encoding="utf-8"))

    public_base = os.environ.get("PUBLIC_BASE", "http://127.0.0.1:8000")
    url = public_base.rstrip("/") + "/webhook"
    resp = requests.post(url, json=data, timeout=10)
    print(resp.status_code)
    print(resp.text)


if __name__ == "__main__":
    main()


