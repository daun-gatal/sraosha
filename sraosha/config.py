from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_FILE_NAME = ".sraosha"


def _find_config_file(explicit_path: str | None = None) -> Path | None:
    """Resolve the config file path.

    Resolution order:
    1. Explicit path (from ``--config`` CLI flag)
    2. ``SRAOSHA_CONFIG`` environment variable
    3. ``.sraosha`` in the current working directory
    4. ``~/.sraosha`` in the user's home directory
    """
    if explicit_path:
        p = Path(explicit_path).expanduser()
        return p if p.is_file() else None

    env_path = os.environ.get("SRAOSHA_CONFIG")
    if env_path:
        p = Path(env_path).expanduser()
        return p if p.is_file() else None

    cwd_file = Path.cwd() / CONFIG_FILE_NAME
    if cwd_file.is_file():
        return cwd_file

    home_file = Path.home() / CONFIG_FILE_NAME
    if home_file.is_file():
        return home_file

    return None


class SraoshaSettings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://sraosha:sraosha@localhost:5432/sraosha"
    REDIS_URL: str = "redis://localhost:6379/0"

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_KEY: str | None = None

    #: Comma-separated browser origins for CORS, or ``*`` for all (dev-friendly default).
    CORS_ALLOWED_ORIGINS: str = "*"

    CONTRACTS_DIR: str = "./contracts"
    DEFAULT_ENFORCEMENT_MODE: str = "block"

    SLACK_WEBHOOK_URL: str | None = None
    SLACK_ENABLED: bool = False

    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None
    EMAIL_ENABLED: bool = False

    ENCRYPTION_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=True,
        extra="ignore",
    )


def load_settings(config_path: str | None = None) -> SraoshaSettings:
    """Create a ``SraoshaSettings`` instance with the resolved config file."""
    found = _find_config_file(config_path)
    if found:
        env_path = found

        class SraoshaSettingsFromFile(SraoshaSettings):
            model_config = SettingsConfigDict(
                env_file=env_path,
                env_file_encoding="utf-8",
                case_sensitive=True,
                extra="ignore",
            )

        return SraoshaSettingsFromFile()
    return SraoshaSettings()


settings: SraoshaSettings = load_settings()


def reload_settings(config_path: str | None = None) -> None:
    """Re-initialise the global ``settings`` singleton (used by CLI ``--config``)."""
    global settings  # noqa: PLW0603
    settings = load_settings(config_path)
