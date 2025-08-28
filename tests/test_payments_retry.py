import asyncio
import types

from app.services.payments import send_pro_invoice


class DummyMessage:
    def __init__(self) -> None:
        self.calls = 0

    async def reply_invoice(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        raise RuntimeError("fail")

    async def reply_text(self, txt: str):  # type: ignore[no-untyped-def]
        return None


class DummyUpdate:
    def __init__(self) -> None:
        self.effective_message = DummyMessage()
        self.effective_user = types.SimpleNamespace(id=123)


class DummyContext:
    application = types.SimpleNamespace()
    bot = types.SimpleNamespace()


def test_send_pro_invoice_retries(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "x")
    update = DummyUpdate()
    ctx = DummyContext()

    async def run():
        await send_pro_invoice(update, ctx)  # should attempt 3 times and then fail open path

    asyncio.run(run())
    assert update.effective_message.calls == 3
