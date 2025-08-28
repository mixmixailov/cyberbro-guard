from __future__ import annotations

import logging
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self) -> None:
        s = get_settings()
        self._scheduler = BackgroundScheduler(timezone=s.SCHED_TIMEZONE)
        self._started = False

    def add_cron(self, func: Callable[[], None], expression: str, name: str) -> None:
        trigger = CronTrigger.from_crontab(expression)
        self._scheduler.add_job(
            func, trigger, name=name, max_instances=1, coalesce=True, misfire_grace_time=60
        )

    def start(self) -> None:
        if not self._started:
            self._scheduler.start()
            self._started = True

    def shutdown(self) -> None:
        try:
            self._scheduler.shutdown(wait=False)
        except Exception:
            pass
