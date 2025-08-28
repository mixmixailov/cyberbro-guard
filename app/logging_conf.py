from __future__ import annotations

import logging

from app.utils.logging import install_json_logging


def setup_logging(debug: bool = False) -> None:
    install_json_logging(debug=debug)

    # Ensure FastAPI/uvicorn access logs don't overwhelm output when not debugging
    if not debug:
        logging.getLogger("uvicorn.error").setLevel(logging.INFO)
        logging.getLogger("uvicorn.access").setLevel(logging.INFO)
