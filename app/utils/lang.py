from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import get_settings


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_catalogs() -> dict[str, dict[str, str]]:
    base_dir = Path(__file__).resolve().parents[2] / "i18n"
    catalogs: dict[str, dict[str, str]] = {}
    for lang in ("ru", "en"):
        path = base_dir / f"{lang}.yml"
        try:
            if path.exists():
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                if isinstance(data, dict):
                    catalogs[lang] = {str(k): str(v) for k, v in data.items()}
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to load i18n file %s: %s", path, exc)
    return catalogs


def t(key: str, lang: str | None = None, **kwargs: Any) -> str:
    """Simple i18n lookup with formatting placeholders.

    If key is missing in selected language, falls back to default locale,
    then to key itself.
    """
    settings = get_settings()
    selected = (lang or settings.DEFAULT_LOCALE or "ru").lower()
    catalogs = _load_catalogs()
    text = (
        catalogs.get(selected, {}).get(key)
        or catalogs.get(settings.DEFAULT_LOCALE, {}).get(key)
        or catalogs.get("en", {}).get(key)
        or key
    )
    try:
        return text.format(**kwargs)
    except Exception:
        return text



