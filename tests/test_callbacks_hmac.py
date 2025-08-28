from app.utils.callbacks import build_v1, verify_v1


def test_build_and_verify_v1_ok(monkeypatch):
    # Ensure secret for deterministic signature
    monkeypatch.setenv("WEBHOOK_SECRET", "secret")
    token = build_v1(["s", "toggle", "welcome", "1"])
    ok, parts = verify_v1(token)
    assert ok
    assert parts[0] == "s"
    assert parts[1] == "toggle"
    assert parts[2] == "welcome"
    assert parts[3] == "1"


def test_verify_v1_ttl_fail(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "secret")
    # Craft an expired token by replacing ts
    token = build_v1(["s", "info"])  # v1:ts:...
    parts = token.split(":")
    parts[1] = str(int(parts[1]) - 999999)  # very old
    expired = ":".join(parts)
    ok, _ = verify_v1(expired)
    assert not ok
