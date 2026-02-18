"""
Core configuration for West Africa Financial Intelligence Agent.

All configuration loaded from environment variables.
"""

import os
from pathlib import Path as _Path

# Load .env if available
_env_path = _Path(__file__).parent.parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass

from typing import Optional


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get environment variable with optional default."""
    return os.environ.get(key, default)


def get_env_required(key: str) -> str:
    """Get required environment variable. Raises if not set."""
    value = os.environ.get(key)
    if not value:
        raise ValueError(f"Required environment variable {key} is not set")
    return value


def get_env_int(key: str, default: int = 0) -> int:
    """Get integer environment variable."""
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default


def get_env_float(key: str, default: float = 0.0) -> float:
    """Get float environment variable."""
    try:
        return float(os.environ.get(key, str(default)))
    except ValueError:
        return default


def get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean environment variable."""
    val = os.environ.get(key, str(default)).lower()
    return val in ("true", "1", "yes", "on")


class Settings:
    """Application settings."""

    # Project
    PROJECT_NAME: str = "West Africa Financial Intelligence Agent"
    DEBUG: bool = get_env_bool("DEBUG", False)
    LOG_LEVEL: str = get_env("LOG_LEVEL", "INFO")

    # Database
    DATABASE_URL: str = get_env(
        "DATABASE_URL",
        f"sqlite:///{_Path(__file__).parent.parent / 'data' / 'finagent.db'}",
    )
    USE_SQLITE: bool = "sqlite" in get_env("DATABASE_URL", "sqlite")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = get_env("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ALLOWED_USERS: str = get_env("TELEGRAM_ALLOWED_USERS", "")  # Comma-separated IDs
    TELEGRAM_WEBHOOK_URL: str = get_env("TELEGRAM_WEBHOOK_URL", "")

    # AI / LLM (Ollama for local, or openai/anthropic for cloud)
    OLLAMA_HOST: str = get_env("OLLAMA_HOST", "http://localhost:11434")
    LLM_PROVIDER: str = get_env("LLM_PROVIDER", "ollama")  # ollama, openai, anthropic
    LLM_MODEL: str = get_env("LLM_MODEL", "llama3.2")
    OPENAI_API_KEY: str = get_env("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = get_env("ANTHROPIC_API_KEY", "")
    TAVILY_API_KEY: str = get_env("TAVILY_API_KEY", "")

    # Web Search & Scraping - Primary BRVM data sources
    BRVM_STOCKS_URLS: tuple = (
        "https://www.richbourse.com/common/variation/index",
        "https://www.dabafinance.com/en/capitalmarkets",
    )
    BRVM_STOCKS_URL: str = "https://www.richbourse.com/common/variation/index"  # default/first
    REQUEST_TIMEOUT: int = get_env_int("REQUEST_TIMEOUT", 30)

    # Alerts
    ALERT_LOSS_THRESHOLD_PCT: float = get_env_float("ALERT_LOSS_THRESHOLD_PCT", 5.0)
    ALERT_GAIN_THRESHOLD_PCT: float = get_env_float("ALERT_GAIN_THRESHOLD_PCT", 10.0)
    ALERT_PRICE_CHECK_INTERVAL_MIN: int = get_env_int("ALERT_PRICE_CHECK_INTERVAL_MIN", 60)
    ALERT_PORTFOLIO_CHECK_HOUR: int = get_env_int("ALERT_PORTFOLIO_CHECK_HOUR", 9)
    ALERT_NEWS_CHECK_HOUR: int = get_env_int("ALERT_NEWS_CHECK_HOUR", 8)

    @classmethod
    def is_telegram_user_allowed(cls, telegram_id: str) -> bool:
        """Check if Telegram user is allowed (whitelist). Empty = allow all."""
        if not cls.TELEGRAM_ALLOWED_USERS:
            return True
        return str(telegram_id) in [u.strip() for u in cls.TELEGRAM_ALLOWED_USERS.split(",") if u.strip()]


settings = Settings()
