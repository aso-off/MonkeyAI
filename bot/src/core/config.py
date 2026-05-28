from functools import lru_cache
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIGS_DIR = Path("/app/configs")
LOCALES_DIR = Path("/app/src/locales")
STATIC_DIR  = Path("/app/static")


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

    # .env secrets
    telegram_token: SecretStr
    admin_ids: list[int] = []
    openai_api_key: SecretStr
    webhook_host: str
    webhook_secret: SecretStr

    # PostgreSQL (.env)
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str
    postgres_user: str
    postgres_password: SecretStr

    # SSH для сбора системной инфо (.env, опционально)
    ssh_hostname: str | None = None
    ssh_username: str | None = None
    ssh_password: SecretStr | None = None
    ssh_timeout: int = 10
    ssh_project_path: str = "/root/bot"

    # config.yml
    whitelist_mode: bool = True
    allowed_user_ids: list[int] = []
    n_chat_modes_per_page: int = 5
    enable_message_streaming: bool = True
    enable_content_moderation: bool = True
    openai_api_base: str | None = None
    return_n_generated_images: int = 1
    image_size: str = "1024x1024"
    image_quality: str = "medium"
    chatgpt_price_per_1000_tokens: float = 0.00275
    gpt_price_per_1000_tokens: float = 0.01
    whisper_price_per_1_min: float = 0.006
    moderation_thresholds: dict[str, float] = {}
    ssh_connection: dict[str, Any] = {}
    webapp_url: str = ""
    bot_version: str = "1.9.1"
    bot_creation_date: str = "2025-02-01"
    container_names: list[str] = []

    # chat_modes.yml / models.yml / locales
    chat_modes: dict[str, Any] = {}
    models: dict[str, Any] = {}
    locales: dict[str, Any] = {}

    # Статика (пути к файлам)
    help_group_chat_video_path: Path = STATIC_DIR / "help_group_chat.mp4"

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Any) -> list[int]:
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, list):
            return [int(x) for x in v]
        return []

    @model_validator(mode="after")
    def load_yaml_configs(self) -> Self:
        cfg = _load_yaml(CONFIGS_DIR / "config.yml")

        self.whitelist_mode              = cfg.get("whitelist_mode", self.whitelist_mode)

        user_ids_cfg = _load_yaml(CONFIGS_DIR / "user-ids.yml") or {}
        self.allowed_user_ids = [int(x) for x in user_ids_cfg.get("allowed_user_ids", [])]
        if "admin_user_ids" in user_ids_cfg:
            self.admin_ids = [int(x) for x in user_ids_cfg.get("admin_user_ids", [])]
        self.n_chat_modes_per_page       = cfg.get("n_chat_modes_per_page", self.n_chat_modes_per_page)
        self.enable_message_streaming    = cfg.get("enable_message_streaming", self.enable_message_streaming)
        self.enable_content_moderation   = cfg.get("enable_content_moderation", self.enable_content_moderation)
        self.openai_api_base             = cfg.get("openai_api_base") or None
        self.return_n_generated_images   = cfg.get("return_n_generated_images", self.return_n_generated_images)
        self.image_size                  = cfg.get("image_size", self.image_size)
        self.image_quality               = cfg.get("image_quality", self.image_quality)
        self.chatgpt_price_per_1000_tokens = cfg.get("chatgpt_price_per_1000_tokens", self.chatgpt_price_per_1000_tokens)
        self.gpt_price_per_1000_tokens   = cfg.get("gpt_price_per_1000_tokens", self.gpt_price_per_1000_tokens)
        self.whisper_price_per_1_min     = cfg.get("whisper_price_per_1_min", self.whisper_price_per_1_min)
        self.moderation_thresholds       = cfg.get("moderation_thresholds", {}) or {}
        # SSH из env-переменных (config.yml больше не используется для SSH)
        if self.ssh_hostname:
            self.ssh_connection = {
                "hostname": self.ssh_hostname,
                "username": self.ssh_username,
                "password": self.ssh_password.get_secret_value() if self.ssh_password else None,
                "timeout": self.ssh_timeout,
                "project_path": self.ssh_project_path,
            }
        self.webapp_url                  = cfg.get("webapp_url", "") or ""
        self.container_names             = cfg.get("container_names", []) or []

        ver = _load_yaml(CONFIGS_DIR / "version.yml") or {}
        self.bot_version        = str(ver.get("version", self.bot_version))
        self.bot_creation_date  = str(ver.get("creation_date", self.bot_creation_date))

        self.chat_modes = _load_yaml(CONFIGS_DIR / "chat_modes.yml")
        self.models     = _load_yaml(CONFIGS_DIR / "models.yml")

        self.locales = {}
        for locale_file in LOCALES_DIR.glob("*.yml"):
            self.locales.update(_load_yaml(locale_file))

        return self

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}"
            f":{self.postgres_password.get_secret_value()}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_host}/webhook"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()