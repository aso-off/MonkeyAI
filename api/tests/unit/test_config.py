"""
Тесты для api/src/core/config.py.

Стратегия: загружаем РЕАЛЬНЫЙ модуль через importlib.util, минуя stub из conftest.
builtins.open перехватывается выборочно (только yaml-файлы), env-переменные
задаются через monkeypatch/os.environ. coverage.py считает строки по file-path,
поэтому выполнение через importlib всё равно попадает в отчёт.
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

_API_SRC = Path(__file__).resolve().parents[2] / "src"
_CONFIG_FILE = _API_SRC / "core" / "config.py"

_BASE_YAML: dict[str, str] = {
    "user-ids.yml": "admin_user_ids:\n- 123456789\nallowed_user_ids:\n- 987654321\n",
    "config.yml": (
        "enable_content_moderation: true\n"
        "return_n_generated_images: 2\n"
        "image_size: 1024x1024\n"
        "image_quality: medium\n"
        "imgbb_api_key: \"\"\n"
    ),
    "chat_modes.yml": "assistant:\n  prompt_start: You are a helpful assistant.\n",
    "models.yml": "available_text_models:\n- gpt-4o\n",
}

# Helpers

def _open_mock(yaml_map: dict):
    """builtins.open, который для .yml возвращает StringIO, иначе - реальный open."""
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

def _load_config_module(env: dict, yaml_map: dict | None = None):
    if yaml_map is None:
        yaml_map = _BASE_YAML
    spec = importlib.util.spec_from_file_location(
        f"_real_api_config_{fake.lexify('????')}", _CONFIG_FILE
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, env, clear=False):
        with mock.patch("builtins.open", side_effect=_open_mock(yaml_map)):
            spec.loader.exec_module(module)
    return module

def _base_env() -> dict:
    return {
        "OPENAI_API_KEY": f"sk-{fake.sha256()[:32]}",
        "POSTGRES_DB": fake.word(),
        "POSTGRES_USER": fake.user_name(),
        "POSTGRES_PASSWORD": fake.sha256()[:24],
        "TELEGRAM_TOKEN": f"{fake.random_int(10**8, 10**9 - 1)}:{fake.sha256()[:35]}",
    }

# Fixtures

@pytest.fixture(scope="module")
def cfg():
    """Загруженный модуль + env для повторных вызовов."""
    admin_id = fake.random_int(min=100_000_000, max=999_999_999)
    allowed_id = fake.random_int(min=100_000_000, max=999_999_999)
    yaml_map = dict(_BASE_YAML)
    yaml_map["user-ids.yml"] = (
        f"admin_user_ids:\n- {admin_id}\nallowed_user_ids:\n- {allowed_id}\n"
    )
    env = _base_env()
    module = _load_config_module(env, yaml_map)
    return module, env, admin_id, allowed_id

# _load_yaml

class TestLoadYaml:

    def test_returns_dict_for_yaml_content(self, cfg) -> None:
        module, *_ = cfg
        with mock.patch("builtins.open", side_effect=_open_mock(_BASE_YAML)):
            result = module._load_yaml(Path("user-ids.yml"))
        assert isinstance(result, dict)
        assert "admin_user_ids" in result

    def test_empty_file_returns_none(self, cfg) -> None:
        module, *_ = cfg
        with mock.patch("builtins.open", side_effect=_open_mock({"empty.yml": ""})):
            result = module._load_yaml(Path("empty.yml"))
        assert result is None

    def test_parses_list_of_faker_ids(self, cfg) -> None:
        module, *_ = cfg
        uid1 = fake.random_int(min=100_000_000, max=999_999_999)
        uid2 = fake.random_int(min=100_000_000, max=999_999_999)
        content = f"ids:\n- {uid1}\n- {uid2}\n"
        with mock.patch("builtins.open", side_effect=_open_mock({"ids.yml": content})):
            result = module._load_yaml(Path("ids.yml"))
        assert result["ids"] == [uid1, uid2]

    def test_parses_nested_dict(self, cfg) -> None:
        module, *_ = cfg
        key = fake.word()
        val = fake.sentence()
        content = f"section:\n  {key}: \"{val}\"\n"
        with mock.patch("builtins.open", side_effect=_open_mock({"nested.yml": content})):
            result = module._load_yaml(Path("nested.yml"))
        assert result["section"][key] == val

# parse_admin_ids validator

class TestParseAdminIds:

    def test_string_csv_converted_to_list(self, cfg) -> None:
        module, *_ = cfg
        uid1 = fake.random_int(min=100_000_000, max=999_999_999)
        uid2 = fake.random_int(min=100_000_000, max=999_999_999)
        result = module.Settings.parse_admin_ids(f"{uid1},{uid2}")
        assert result == [uid1, uid2]

    def test_string_with_spaces(self, cfg) -> None:
        module, *_ = cfg
        uid = fake.random_int(min=100_000_000, max=999_999_999)
        result = module.Settings.parse_admin_ids(f"  {uid}  ")
        assert result == [uid]

    def test_empty_string_returns_empty_list(self, cfg) -> None:
        module, *_ = cfg
        assert module.Settings.parse_admin_ids("") == []

    def test_list_input_converted(self, cfg) -> None:
        module, *_ = cfg
        uids = [fake.random_int(min=100_000_000, max=999_999_999) for _ in range(3)]
        result = module.Settings.parse_admin_ids(uids)
        assert result == uids

    def test_none_returns_empty_list(self, cfg) -> None:
        module, *_ = cfg
        assert module.Settings.parse_admin_ids(None) == []

    def test_faker_batch_ids(self, cfg) -> None:
        module, *_ = cfg
        for _ in range(5):
            uid = fake.random_int(min=100_000_000, max=999_999_999)
            result = module.Settings.parse_admin_ids(str(uid))
            assert result == [uid]

# Свойства database_url / redis_url

class TestSettingsProperties:

    def test_database_url_contains_user_and_db(self, cfg) -> None:
        module, env, *_ = cfg
        url = module.settings.database_url
        assert "postgresql+asyncpg://" in url
        assert env["POSTGRES_USER"] in url
        assert env["POSTGRES_DB"] in url

    def test_database_url_contains_password(self, cfg) -> None:
        module, env, *_ = cfg
        url = module.settings.database_url
        assert env["POSTGRES_PASSWORD"] in url

    def test_redis_url_no_password(self, cfg) -> None:
        module, *_ = cfg
        url = module.settings.redis_url
        assert url.startswith("redis://")

    def test_redis_url_with_password_uses_auth_format(self, cfg) -> None:
        module, env, *_ = cfg
        redis_pwd = fake.sha256()[:16]
        new_env = {**env, "REDIS_PASSWORD": redis_pwd}
        yaml_map = dict(_BASE_YAML)
        with mock.patch.dict(os.environ, new_env, clear=False):
            with mock.patch("builtins.open", side_effect=_open_mock(yaml_map)):
                s = module.Settings()
        url = s.redis_url
        assert redis_pwd in url
        assert "redis://:" in url

    def test_database_url_default_host_and_port(self, cfg) -> None:
        module, *_ = cfg
        url = module.settings.database_url
        assert "localhost" in url or "postgres" in url

# Значения из YAML (load_yaml_configs)

class TestSettingsYamlValues:

    def test_admin_ids_loaded_from_yaml(self, cfg) -> None:
        module, _, admin_id, _ = cfg
        assert admin_id in module.settings.admin_ids

    def test_allowed_user_ids_loaded_from_yaml(self, cfg) -> None:
        module, _, _, allowed_id = cfg
        assert allowed_id in module.settings.allowed_user_ids

    def test_enable_content_moderation_true(self, cfg) -> None:
        module, *_ = cfg
        assert module.settings.enable_content_moderation is True

    def test_return_n_generated_images(self, cfg) -> None:
        module, *_ = cfg
        assert module.settings.return_n_generated_images == 2

    def test_image_size(self, cfg) -> None:
        module, *_ = cfg
        assert module.settings.image_size == "1024x1024"

    def test_chat_modes_loaded(self, cfg) -> None:
        module, *_ = cfg
        assert "assistant" in module.settings.chat_modes

    def test_models_loaded(self, cfg) -> None:
        module, *_ = cfg
        assert isinstance(module.settings.models, dict)

    def test_openai_api_key_is_secret(self, cfg) -> None:
        module, *_ = cfg
        key = module.settings.openai_api_key
        assert hasattr(key, "get_secret_value")

    def test_telegram_token_is_secret(self, cfg) -> None:
        module, *_ = cfg
        tok = module.settings.telegram_token
        assert hasattr(tok, "get_secret_value")

    def test_imgbb_api_key_default_empty(self, cfg) -> None:
        module, *_ = cfg
        assert module.settings.imgbb_api_key == ""

    def test_admin_ids_from_env_string(self, cfg) -> None:
        """admin_ids могут приходить из env как CSV-строка."""
        module, env, *_ = cfg
        uid = fake.random_int(min=100_000_000, max=999_999_999)
        # parse_admin_ids вызывается ДО model_validator > проверяем напрямую
        result = module.Settings.parse_admin_ids(str(uid))
        assert uid in result

# get_settings lru_cache

class TestGetSettings:

    def test_returns_settings_instance(self, cfg) -> None:
        module, *_ = cfg
        assert isinstance(module.settings, module.Settings)

    def test_lru_cache_returns_same_object(self, cfg) -> None:
        module, env, *_ = cfg
        yaml_map = dict(_BASE_YAML)
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch("builtins.open", side_effect=_open_mock(yaml_map)):
                module.get_settings.cache_clear()
                s1 = module.get_settings()
                s2 = module.get_settings()
        assert s1 is s2
        module.get_settings.cache_clear()

    def test_new_instance_after_cache_clear(self, cfg) -> None:
        module, env, *_ = cfg
        yaml_map = dict(_BASE_YAML)
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch("builtins.open", side_effect=_open_mock(yaml_map)):
                module.get_settings.cache_clear()
                s_new = module.get_settings()
        assert isinstance(s_new, module.Settings)
        module.get_settings.cache_clear()
