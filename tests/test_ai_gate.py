import asyncio
from types import SimpleNamespace

from app.services.moderation import ModerationService
from app.metrics import registry, generate_latest


class StubProvider:
    def __init__(self):
        self.calls = 0

    def moderate(self, text: str):  # returns allow
        self.calls += 1
        from app.services.ai_moderation import ModerationResult

        return ModerationResult(allowed=True, action="allow", reason=None)


def make_update(text: str = "hi"):
    user = SimpleNamespace(id=123, language_code="en")
    chat = SimpleNamespace(id=-100, type="group")
    message = SimpleNamespace(text=text, chat=chat, from_user=user)
    return SimpleNamespace(message=message, effective_user=user, effective_chat=chat, update_id=1)


def make_context():
    return SimpleNamespace(application=SimpleNamespace())


def test_ai_pro_invokes_provider(monkeypatch):
    # Env: AI enabled and key present
    monkeypatch.setenv("AI_MODERATION_ENABLED", "true")
    monkeypatch.setenv("AI_MODERATION_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xxx")

    # PRO subscription
    monkeypatch.setattr(
        "app.services.moderation.get_subscription",
        lambda uid, code: {"until": "2099-01-01"},
        raising=True,
    )

    # Stub provider
    prov = StubProvider()
    monkeypatch.setattr("app.services.moderation.get_provider", lambda: prov, raising=True)

    svc = ModerationService()
    upd = make_update("hello")
    ctx = make_context()

    asyncio.run(svc.on_message(upd, ctx))

    assert prov.calls >= 1


def test_ai_free_user_skips(monkeypatch):
    monkeypatch.setenv("AI_MODERATION_ENABLED", "true")
    monkeypatch.setenv("AI_MODERATION_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xxx")

    # Free (no PRO)
    monkeypatch.setattr(
        "app.services.moderation.get_subscription",
        lambda uid, code: None,
        raising=True,
    )

    # Provider should not be called
    prov = StubProvider()
    monkeypatch.setattr("app.services.moderation.get_provider", lambda: prov, raising=True)

    svc = ModerationService()
    upd = make_update("hello")
    ctx = make_context()

    asyncio.run(svc.on_message(upd, ctx))

    assert prov.calls == 0
    # metrics contain skipped reason
    out = generate_latest(registry).decode("utf-8")
    assert "cyberbro_ai_skipped_total" in out and "reason=\"not_pro\"" in out


def test_ai_disabled_behaves_as_before(monkeypatch):
    # AI disabled
    monkeypatch.setenv("AI_MODERATION_ENABLED", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    prov = StubProvider()
    monkeypatch.setattr("app.services.moderation.get_provider", lambda: None, raising=True)

    svc = ModerationService()
    upd = make_update("hello")
    ctx = make_context()

    # Should run without invoking provider
    asyncio.run(svc.on_message(upd, ctx))
    assert prov.calls == 0





