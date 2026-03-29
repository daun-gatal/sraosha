from pydantic_settings import BaseSettings


class SraoshaSettings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://sraosha:sraosha@localhost:5432/sraosha"
    REDIS_URL: str = "redis://localhost:6379/0"

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_KEY: str | None = None

    CONTRACTS_DIR: str = "./contracts"
    DEFAULT_ENFORCEMENT_MODE: str = "block"

    DRIFT_SCAN_INTERVAL_SECONDS: int = 3600
    DRIFT_BASELINE_WINDOW: int = 14

    SLACK_WEBHOOK_URL: str | None = None
    SLACK_ENABLED: bool = False

    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None
    EMAIL_ENABLED: bool = False

    DASHBOARD_URL: str = "http://localhost:5173"

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = SraoshaSettings()
