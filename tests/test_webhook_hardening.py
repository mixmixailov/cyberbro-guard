import json

from fastapi.testclient import TestClient

from app.main import app


def test_webhook_unauthorized_on_bad_secret(monkeypatch):
    # Ensure secret is set
    monkeypatch.setenv("WEBHOOK_SECRET", "s3cr3t")
    monkeypatch.setenv("BOT_TOKEN", "x")
    client = TestClient(app)
    # Missing/invalid secret header
    resp = client.post("/webhook", json={"update_id": 1})
    assert resp.status_code == 401


def test_webhook_payload_too_large(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "")
    monkeypatch.setenv("MAX_WEBHOOK_BODY", "64")
    monkeypatch.setenv("BOT_TOKEN", "x")
    client = TestClient(app)
    # build body larger than limit
    data = {"update_id": 1, "message": {"text": "x" * 100}}
    body = json.dumps(data)
    assert len(body) > 64
    resp = client.post("/webhook", data=body, headers={"content-type": "application/json"})
    assert resp.status_code == 413


def test_webhook_secret_disabled_allows_without_header(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "")
    monkeypatch.setenv("BOT_TOKEN", "x")
    client = TestClient(app)
    resp = client.post("/webhook", json={"update_id": 1})
    assert resp.status_code == 200
    assert resp.json().get("ok") is True


def test_webhook_secret_enabled_requires_header(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "abc")
    monkeypatch.setenv("BOT_TOKEN", "x")
    client = TestClient(app)
    # no header → 401
    resp = client.post("/webhook", json={"update_id": 1})
    assert resp.status_code == 401
    # correct header → 200
    resp2 = client.post(
        "/webhook",
        json={"update_id": 2},
        headers={"X-Telegram-Bot-Api-Secret-Token": "abc"},
    )
    assert resp2.status_code == 200
    assert resp2.json().get("ok") is True
