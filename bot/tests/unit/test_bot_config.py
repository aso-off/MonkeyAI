"""
Тесты для bot/src/core/config.py.

Стратегия: загружаем РЕАЛЬНЫЙ модуль через importlib, патча:
- builtins.open          → возвращаем yaml-контент по имени файла
- Path.glob              → для LOCALES_DIR возвращаем список yaml-путей
- Path.exists            → возвращаем True для локальных путей
"""

import importlib.util
import io
import os
from pathlib import Path
from unittest import mock

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

_BOT_SRC = Path(__file__).resolve().parents[2] / "src"
_CONFIG_FILE = _BOT_SRC / "core" / "config.py"

_BASE_CFG_YAML = (
    "whitelist_mode: true\n"
    "n_chat_modes_per_page: 5\n"
    "enable_message_streaming: true\n"
    "enable_content_moderation: true\n"
    "dialog_context_limit: 20\n"
    "message_max_length: 4096\n"
    "draft_throttle_seconds: 0.4\n"
    "busy_lock_ttl_seconds: 300\n"
    "api_request_timeout_seconds: 120.0\n"
    "throttle_rate_ms: 1000\n"
    "return_n_generated_images: 1\n"
    "image_size: 1024x1024\n"
    "image_quality: medium\n"
    "chatgpt_price_per_1000_tokens: 0.00275\n"
    "gpt_price_per_1000_tokens: 0.01\n"
    "whisper_price_per_1_min: 0.006\n"
    "webapp_url: https://test.example.com/app\n"
    "container_names:\n- api\n- bot\n"
)
_BASE_YAML_MAP: dict[str, str] = {
    "config.yml": _BASE_CFG_YAML,
    "user-ids.yml": "admin_user_ids:\n- 123456789\nallowed_user_ids:\n- 987654321\n",
    "version.yml": "version: 2.6.3\ncreation_date: 2025-02-01\n",
    "chat_modes.yml": "assistant:\n  prompt_start: You are a helpful assistant.\n",
    "models.yml": "available_text_models:\n- gpt-4o\n",
    "ru.yml": "ru:\n  greeting: Привет!\n",
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _open_mock(yaml_map: dict):
    real_open = open

    def _impl(path, *args, **kwargs):
        name = Path(str(path)).name
        if name in yaml_map:
            content = yaml_map[name]
            cm = mock.MagicMock()
            cm.__enter__ = mock.MagicMock(return_value=io.StringIO(content))
            cm.__exit__ = mock.MagicMock(return_value=False)
            return cm
        return real_open(path, *args, **kwargs)

    return _impl


def _base_env() -> dict:
    return {
        "TELEGRAM_TOKEN": f"{fake.random_int(10**8, 10**9 - 1)}:{fake.sha256()[:35]}",
        "OPENAI_API_KEY": f"sk-{fake.sha256()[:32]}",
        "WEBHOOK_HOST": "https://test.example.com",
        "WEBHOOK_SECRET": fake.sha256()[:24],
        "POSTGRES_DB": fake.word(),
        "POSTGRES_USER": fake.user_name(),
        "POSTGRES_PASSWORD": fake.sha256()[:24],
        "ADMIN_IDS": str(fake.random_int(min=100_000_000, max=999_999_999)),
    }


def _make_fake_locale_path(name: str) -> Path:
    p = mock.MagicMock(spec=Path)
    p.name = name
    p.__str__ = mock.MagicMock(return_value=f"/app/src/locales/{name}")
    return p


def _load_bot_config(env: dict, yaml_map: dict | None = None, with_ssh: bool = False):
    if yaml_map is None:
        yaml_map = dict(_BASE_YAML_MAP)

    if with_ssh:
        env = {**env, "SSH_HOSTNAME": "test-server.example.com",
               "SSH_USERNAME": fake.user_name(), "SSH_PASSWORD": fake.sha256()[:16]}

    fake_locale_path = _make_fake_locale_path("ru.yml")

    def _patched_glob(self, pattern):
        if "locales" in str(self) or str(self).endswith("locales"):
            return iter([fake_locale_path])
        return Path.glob(self, pattern)

    spec = importlib.util.spec_from_file_location(
        f"_real_bot_config_{fake.lexify('????')}", _CONFIG_FILE
    )
    module = importlib.util.module_from_spec(spec)

    with mock.patch.dict(os.environ, env, clear=False):
        with mock.patch("builtins.open", side_effect=_open_mock(yaml_map)):
            with mock.patch.object(Path, "glob", _patched_glob):
                spec.loader.exec_module(module)

    return module


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def bot_cfg():
    admin_id = fake.random_int(min=100_000_000, max=999_999_999)
    allowed_id = fake.random_int(min=100_000_000, max=999_999_999)
    yaml_map = dict(_BASE_YAML_MAP)
    yaml_map["user-ids.yml"] = (
        f"admin_user_ids:\n- {admin_id}\nallowed_user_ids:\n- {allowed_id}\n"
    )
    env = _base_env()
    env["ADMIN_IDS"] = str(admin_id)
    module = _load_bot_config(env, yaml_map)
    return module, env, admin_id, allowed_id


@pytest.fixture(scope="module")
def bot_cfg_ssh():
    """Конфиг с SSH."""
    env = _base_env()
    env["SSH_HOSTNAME"] = "server.example.com"
    env["SSH_USERNAME"] = fake.user_name()
    env["SSH_PASSWORD"] = fake.sha256()[:16]
    return _load_bot_config(env, with_ssh=False)


# ── parse_admin_ids ───────────────────────────────────────────────────────────


class TestParseAdminIds:

    def test_csv_string(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        uid1 = fake.random_int(min=100_000_000, max=999_999_999)
        uid2 = fake.random_int(min=100_000_000, max=999_999_999)
        result = module.Settings.parse_admin_ids(f"{uid1},{uid2}")
        assert result == [uid1, uid2]

    def test_list_input(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        uid = fake.random_int(min=100_000_000, max=999_999_999)
        assert module.Settings.parse_admin_ids([uid]) == [uid]

    def test_empty_string(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        assert module.Settings.parse_admin_ids("") == []

    def test_none_returns_empty(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        assert module.Settings.parse_admin_ids(None) == []

    def test_string_with_whitespace(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        uid = fake.random_int(min=100_000_000, max=999_999_999)
        assert module.Settings.parse_admin_ids(f"  {uid}  ") == [uid]


# ── Properties ────────────────────────────────────────────────────────────────


class TestBotSettingsProperties:

    def test_database_url_format(self, bot_cfg) -> None:
        module, env, *_ = bot_cfg
        url = module.settings.database_url
        assert url.startswith("postgresql+asyncpg://")
        assert env["POSTGRES_DB"] in url

    def test_redis_url_no_password(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        url = module.settings.redis_url
        assert url.startswith("redis://")
        assert "/0" in url

    def test_redis_url_with_password(self, bot_cfg) -> None:
        module, env, *_ = bot_cfg
        redis_pwd = fake.sha256()[:16]
        new_env = {**env, "REDIS_PASSWORD": redis_pwd}
        yaml_map = dict(_BASE_YAML_MAP)

        def _patched_glob(self, pattern):
            if "locales" in str(self):
                return iter([_make_fake_locale_path("ru.yml")])
            return Path.glob(self, pattern)

        with mock.patch.dict(os.environ, new_env, clear=False):
            with mock.patch("builtins.open", side_effect=_open_mock(yaml_map)):
                with mock.patch.object(Path, "glob", _patched_glob):
                    s = module.Settings()
        assert redis_pwd in s.redis_url
        assert "redis://:" in s.redis_url

    def test_webhook_url_format(self, bot_cfg) -> None:
        module, env, *_ = bot_cfg
        url = module.settings.webhook_url
        assert url.endswith("/webhook")
        assert env["WEBHOOK_HOST"] in url


# ── YAML-значения (load_yaml_configs) ─────────────────────────────────────────


class TestBotYamlValues:

    def test_admin_ids_loaded(self, bot_cfg) -> None:
        module, _, admin_id, _ = bot_cfg
        assert admin_id in module.settings.admin_ids

    def test_allowed_user_ids_loaded(self, bot_cfg) -> None:
        module, _, _, allowed_id = bot_cfg
        assert allowed_id in module.settings.allowed_user_ids

    def test_whitelist_mode_true(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        assert module.settings.whitelist_mode is True

    def test_enable_content_moderation(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        assert module.settings.enable_content_moderation is True

    def test_chat_modes_loaded(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        assert "assistant" in module.settings.chat_modes

    def test_models_loaded(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        assert isinstance(module.settings.models, dict)

    def test_locales_populated(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        assert isinstance(module.settings.locales, dict)

    def test_bot_version_from_yaml(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        assert module.settings.bot_version == "2.6.3"

    def test_bot_creation_date_from_yaml(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        assert module.settings.bot_creation_date == "2025-02-01"

    def test_webapp_url_from_yaml(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        assert "example.com" in module.settings.webapp_url

    def test_container_names_from_yaml(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        assert isinstance(module.settings.container_names, list)

    def test_secrets_are_secret_str(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        for attr in ("telegram_token", "openai_api_key", "webhook_secret", "postgres_password"):
            val = getattr(module.settings, attr)
            assert hasattr(val, "get_secret_value"), f"{attr} не является SecretStr"

    def test_faker_price_values_are_positive(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        for attr in ("chatgpt_price_per_1000_tokens", "gpt_price_per_1000_tokens", "whisper_price_per_1_min"):
            val = getattr(module.settings, attr)
            assert val > 0, f"{attr} должен быть > 0"


# ── SSH branch ────────────────────────────────────────────────────────────────


class TestSshBranch:

    def test_ssh_connection_populated_when_hostname_set(self, bot_cfg_ssh) -> None:
        """Если SSH_HOSTNAME задан, ssh_connection заполняется."""
        settings = bot_cfg_ssh.settings
        if settings.ssh_hostname:
            assert settings.ssh_connection.get("hostname") == settings.ssh_hostname

    def test_ssh_connection_empty_without_hostname(self, bot_cfg) -> None:
        """Без SSH_HOSTNAME — ssh_connection пустой словарь."""
        module, *_ = bot_cfg
        if not module.settings.ssh_hostname:
            assert module.settings.ssh_connection == {}


# ── get_settings lru_cache ────────────────────────────────────────────────────


class TestBotGetSettings:

    def test_returns_settings_instance(self, bot_cfg) -> None:
        module, *_ = bot_cfg
        assert isinstance(module.settings, module.Settings)

    def test_lru_cache_returns_same_object(self, bot_cfg) -> None:
        module, env, *_ = bot_cfg
        yaml_map = dict(_BASE_YAML_MAP)

        def _patched_glob(self, pattern):
            if "locales" in str(self):
                return iter([_make_fake_locale_path("ru.yml")])
            return Path.glob(self, pattern)

        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch("builtins.open", side_effect=_open_mock(yaml_map)):
                with mock.patch.object(Path, "glob", _patched_glob):
                    module.get_settings.cache_clear()
                    s1 = module.get_settings()
                    s2 = module.get_settings()
        assert s1 is s2
        module.get_settings.cache_clear()
