from __future__ import annotations

import logging
from logging.config import dictConfig


def setup_logging(debug: bool = False) -> None:
    level = "DEBUG" if debug else "INFO"
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                }
            },
            "root": {
                "level": level,
                "handlers": ["console"],
            },
        }
    )

    # Ensure FastAPI/uvicorn access logs don't overwhelm output when not debugging
    if not debug:
        logging.getLogger("uvicorn.error").setLevel(logging.INFO)
        logging.getLogger("uvicorn.access").setLevel(logging.INFO)






