from __future__ import annotations

import uuid
from typing import Callable

from starlette.types import ASGIApp, Receive, Scope, Send

from app.utils.logging import set_request_id


class CorrelationMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:  # noqa: D401
        if scope["type"] == "http":
            request_id = str(uuid.uuid4())
            set_request_id(request_id)
            scope.setdefault("headers", [])
        await self.app(scope, receive, send)








































