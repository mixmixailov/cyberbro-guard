"""Handlers package setup for CyberBro Guard bot."""

from telegram.ext import Application

from .basic import register as register_basic


def setup_handlers(app: Application) -> None:
    """Register all handlers on the provided PTB Application."""
    register_basic(app)




