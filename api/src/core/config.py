import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIGS_DIR = Path(os.environ.get("MONKEY_CONFIGS_DIR", "/app/configs"))


def _load_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="/app/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenAI
    openai_api_key: SecretStr
    openai_api_base: str | None = None

    # PostgreSQL
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str
    postgres_user: str
    postgres_password: SecretStr

    # Пул соединений к БД (дефолты = прод)
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: SecretStr | None = None

    # Auth - список admin-id из user-ids.yml
    admin_ids: list[int] = []
    allowed_user_ids: list[int] = []

    # Telegram Mini App secret (для проверки initData)
    telegram_token: SecretStr

    # Конфигурация из YAML-файлов
    chat_modes: dict[str, Any] = {}
    models: dict[str, Any] = {}
    enable_content_moderation: bool = True
    moderation_thresholds: dict[str, float] = {}
    return_n_generated_images: int = 1
    image_size: str = "1024x1024"
    image_quality: str = "medium"
    image_rate_limit_count: int = 15
    image_rate_limit_window_seconds: int = 3600
    # ImgBB API key for uploading generated images to permanent CDN storage.
    imgbb_api_key: str = ""

    # Retention
    retention_enabled: bool = True
    retention_dialogs_inactive_days: int = 90
    retention_reactions_days: int = 90
    retention_interval_hours: int = 24
    retention_batch_size: int = 500

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Any) -> list[int]:
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, list):
            return [int(x) for x in v]
        return []

    @model_validator(mode="after")
    def load_yaml_configs(self):
        user_ids_cfg = _load_yaml(CONFIGS_DIR / "user-ids.yml") or {}
        self.allowed_user_ids = [int(x) for x in user_ids_cfg.get("allowed_user_ids", [])]
        if "admin_user_ids" in user_ids_cfg:
            self.admin_ids = [int(x) for x in user_ids_cfg.get("admin_user_ids", [])]

        cfg = _load_yaml(CONFIGS_DIR / "config.yml") or {}
        self.enable_content_moderation = cfg.get("enable_content_moderation", self.enable_content_moderation)
        self.moderation_thresholds = cfg.get("moderation_thresholds", {}) or {}
        self.openai_api_base = cfg.get("openai_api_base") or None
        self.return_n_generated_images = cfg.get("return_n_generated_images", self.return_n_generated_images)
        self.image_size = cfg.get("image_size", self.image_size)
        self.image_quality = cfg.get("image_quality", self.image_quality)
        self.image_rate_limit_count = cfg.get("image_rate_limit_count", self.image_rate_limit_count)
        self.image_rate_limit_window_seconds = cfg.get(
            "image_rate_limit_window_seconds", self.image_rate_limit_window_seconds
        )

        ret = cfg.get("retention") or {}
        self.retention_enabled = ret.get("enabled", self.retention_enabled)
        self.retention_dialogs_inactive_days = ret.get(
            "dialogs_inactive_days", self.retention_dialogs_inactive_days
        )
        self.retention_reactions_days = ret.get("reactions_days", self.retention_reactions_days)
        self.retention_interval_hours = ret.get("interval_hours", self.retention_interval_hours)
        self.retention_batch_size = ret.get("batch_size", self.retention_batch_size)

        self.chat_modes = _load_yaml(CONFIGS_DIR / "chat_modes.yml") or {}
        self.models = _load_yaml(CONFIGS_DIR / "models.yml") or {}
        return self

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}"
            f":{self.postgres_password.get_secret_value()}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            pwd = self.redis_password.get_secret_value()
            return f"redis://:{pwd}@{self.redis_host}:{self.redis_port}"
        return f"redis://{self.redis_host}:{self.redis_port}"


@lru_cache
def get_settings() -> Settings:
    # значения берутся из env (pydantic-settings)
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
