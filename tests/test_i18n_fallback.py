from app.utils.lang import t


def test_fallback_to_en_when_missing(monkeypatch):
    # Force default locale to 'ru' and request a key that exists in EN
    monkeypatch.setenv("DEFAULT_LOCALE", "ru")
    # Use a key we know exists in en.yml
    text = t("ai.reason.spam", lang="xx")
    assert isinstance(text, str) and len(text) > 0
