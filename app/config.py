from typing import Iterable

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    # empty allowed for local mock run
    BOT_TOKEN: str = ""
    PUBLIC_BASE: str | None = None
    DEBUG: bool = False

    # Webhook security
    WEBHOOK_SECRET: str | None = None
    WEBHOOK_HANDLE_TIMEOUT_S: float = 8.0
    # Webhook URL composition and mode
    PUBLIC_URL: str | None = None
    WEBHOOK_PATH: str = "/webhook"
    USE_WEBHOOK: bool = True
    USE_POLLING: bool = False
    # Debug: process webhook updates inline (bypass queue/worker)
    WEBHOOK_INLINE_PROCESS: bool = False
    WEBHOOK_FORCE_REPLY_TEST: bool = False

    # Admins
    ADMIN_IDS: set[int] = set()

    # Locales
    DEFAULT_LOCALE: str = "ru"

    # Payments (Telegram Stars)
    PAYMENTS_STARS_ENABLED: bool = False
    PAYMENTS_STARS_TEST: bool = False
    PRO_PRICE_XTR: int = 4900
    PRO_PERIOD_DAYS: int = 30
    PAYMENTS_FAIL_OPEN: bool = True
    REFUND_WINDOW_H: int = 24

    # Moderation defaults (global fallbacks; per-chat overrides live in DB)
    FLOOD_N: int = 6
    FLOOD_WINDOW_S: int = 10
    REPEAT_N: int = 3
    REPEAT_WINDOW_S: int = 60
    CAPTCHA_TTL_S: int = 60
    WARNS_LIMIT_24H: int = 3
    BAN_DAYS: int = 7
    LINK_POLICY: str = "restricted"  # restricted|allow|block_all
    WELCOME_ENABLED: bool = True

    # Allowed updates for webhook setup script convenience
    ALLOWED_UPDATES: tuple[str, ...] = (
        "message",
        "edited_message",
        "callback_query",
        "chat_member",
        "my_chat_member",
        "message_reaction",
        "chat_join_request",
        "pre_checkout_query",
    )

    # AI moderation
    AI_MODERATION_ENABLED: bool = False
    AI_MODERATION_PROVIDER: str = "openai"
    OPENAI_API_KEY: str | None = None
    AI_MODERATION_ACTION_ON_FLAG: str = "block"  # block|flag|allow
    AI_MODERATION_APPLIES_TO: str = "inbound"  # inbound|outbound|both
    AI_MODERATION_FAIL_OPEN: bool = True
    AI_MONTHLY_QUOTA: int = 20000  # per chat, soft limit

    # Scheduler
    SCHED_ENABLED: bool = True
    SCHED_TIMEZONE: str = "UTC"
    SCHED_CRON_REMINDERS: str = "*/10 * * * *"
    SCHED_CRON_EXPIRE: str = "*/5 * * * *"
    SCHED_CRON_CLEANUP: str = "0 4 * * *"

    # DB migrations
    AUTO_MIGRATE: bool = False

    # Security
    MAX_WEBHOOK_BODY: int = 1024 * 1024  # 1 MB
    CALLBACK_TTL_S: int = 600
    IDMP_TTL_SEC: int = 172800

    # Rate limit scope for callback abuse protection
    RATE_LIMIT_SCOPE: str = "user"  # user|user_chat

    # Cleanup thresholds (days)
    CLEANUP_USERSTATE_DAYS: int = 7
    CLEANUP_REMINDERS_DAYS: int = 30
    CLEANUP_TICKETS_DAYS: int = 90

        # Exponential backoff for outbound API calls (send_queue)
    BACKOFF_BASE: float = 0.5  # Base backoff delay in seconds
    BACKOFF_MAX: float = 20.0  # Maximum backoff delay in seconds
    BACKOFF_JITTER: str = "full"  # Jitter type: full|none|decorrelated
    
    # Telegram API configuration for testing
    TELEGRAM_API_BASE: str = "https://api.telegram.org"  # Can be overridden for testing
    
    # Database backup configuration
    BACKUP_RETENTION: int = 7  # Keep last N backup files

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("WEBHOOK_SECRET")
    @classmethod
    def _validate_webhook_secret(cls, v: str | None, info) -> str | None:
        """Validate WEBHOOK_SECRET is set in production mode."""
        # Get DEBUG value from the same validation context
        debug_value = info.data.get("DEBUG", False)
        
        if not debug_value and not (v or "").strip():
            raise ValueError(
                "WEBHOOK_SECRET is required when DEBUG is false. "
                "Set WEBHOOK_SECRET environment variable for production security."
            )
        return v

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def _parse_admin_ids(cls, v: object) -> set[int]:
        if isinstance(v, set):
            return {int(x) for x in v}
        if isinstance(v, (list, tuple)):
            return {int(x) for x in v}
        if isinstance(v, str):
            items: Iterable[str] = (p.strip() for p in v.split(",") if p.strip())
            return {int(p) for p in items}
        if v is None:
            return set()
        # Fallback: try to cast single value
        try:
            return {int(v)}  # type: ignore[arg-type]
        except Exception:
            return set()

    def require_token(self) -> None:
        """Ensure BOT_TOKEN is present in non-DEBUG mode."""
        if not self.DEBUG and not (self.BOT_TOKEN or "").strip():
            raise ValueError("BOT_TOKEN is required when DEBUG is false")


def get_settings() -> Settings:
    # Return fresh Settings each call to reflect environment changes during tests/runtime
    return Settings()
