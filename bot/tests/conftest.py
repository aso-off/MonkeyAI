"""
Общий conftest для bot/tests/.

КРИТИЧНО: sys.modules["src.core.config"] должен быть проставлен ДО того,
как pytest импортирует любой bot-модуль. Иначе строка

    settings = get_settings()   # bot/src/core/config.py, module level

попытается прочитать /app/.env и /app/configs/*.yml — файлы,
которых нет в локальном окружении → ValidationError → ImportError.
"""

import logging
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiogram.types import Message

import pytest
from faker import Faker

# ── sys.path ──────────────────────────────────────────────────────────────────

_BOT_DIR = Path(__file__).resolve().parents[1]
# Добавляем только bot/ — бот-модули используют "from src.X import ...",
# поэтому bot/src в sys.path не нужен и конфликтует с api/src (одинаковые имена: schemas, core).
if str(_BOT_DIR) not in sys.path:
    sys.path.insert(0, str(_BOT_DIR))

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_fake_settings() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        telegram_token=types.SimpleNamespace(get_secret_value=lambda: "1234567890:test_token"),
        admin_ids=[123456789],
        openai_api_key=types.SimpleNamespace(get_secret_value=lambda: "sk-test-key"),
        webhook_host="https://test.example.com",
        webhook_secret=types.SimpleNamespace(get_secret_value=lambda: "webhook_secret"),
        whitelist_mode=True,
        allowed_user_ids=[],
        n_chat_modes_per_page=5,
        enable_message_streaming=True,
        enable_content_moderation=True,
        dialog_context_limit=20,
        message_max_length=4096,
        draft_throttle_seconds=0.4,
        busy_lock_ttl_seconds=300,
        api_request_timeout_seconds=120.0,
        throttle_rate_ms=1000,
        openai_api_base=None,
        return_n_generated_images=1,
        image_size="1024x1024",
        image_quality="medium",
        chatgpt_price_per_1000_tokens=0.00275,
        gpt_price_per_1000_tokens=0.01,
        whisper_price_per_1_min=0.006,
        moderation_thresholds={},
        ssh_connection={},
        ssh_hostname=None,
        webapp_url="https://test.example.com/app",
        bot_version="2.6.21",
        bot_creation_date="2025-02-01",
        container_names=[],
        chat_modes={
            "assistant": {"prompt_start": "You are a helpful assistant."},
            "code_assistant": {"prompt_start": "You are a coding expert."},
        },
        models={},
        locales={
            "ru": {
                "greeting": "Привет!",
                "access_denied": "Доступ запрещён.",
                "error": "Произошла ошибка.",
                "hello": "Привет, {name}!",
            },
            "en": {
                "greeting": "Hello!",
                "access_denied": "Access denied.",
                "error": "An error occurred.",
                "hello": "Hello, {name}!",
            },
            "de": {"greeting": "Hallo!"},
        },
        help_group_chat_video_path=Path("/tmp/help.mp4"),
        postgres_host="localhost",
        postgres_port=5432,
        postgres_db="testdb",
        postgres_user="user",
        postgres_password=types.SimpleNamespace(get_secret_value=lambda: "password"),
        database_url="postgresql+asyncpg://user:password@localhost:5432/testdb",
        redis_host="localhost",
        redis_port=6379,
        redis_password=None,
        redis_url="redis://localhost:6379/0",
    )


# ── КРИТИЧЕСКИЙ ФИX: stub src.core.config до любого импорта bot-модулей ───────

_fake_settings_singleton = _make_fake_settings()

_stub_config: Any = types.ModuleType("src.core.config")
_stub_config.settings = _fake_settings_singleton
_stub_config.get_settings = lambda: _fake_settings_singleton
sys.modules["src.core.config"] = _stub_config

_stub_config_short: Any = types.ModuleType("core.config")
_stub_config_short.settings = _fake_settings_singleton
_stub_config_short.get_settings = lambda: _fake_settings_singleton
sys.modules.setdefault("core.config", _stub_config_short)

_stub_logger: Any = types.ModuleType("src.core.logger")
_stub_logger.logger = logging.getLogger("bot_test")
sys.modules.setdefault("src.core.logger", _stub_logger)

# ── Fixtures ──────────────────────────────────────────────────────────────────

Faker.seed(42)


@pytest.fixture(scope="session")
def fake() -> Faker:
    """Faker с ru_RU + en_US локалями. Session-scoped — создаётся один раз."""
    return Faker(["ru_RU", "en_US"])


@pytest.fixture
def fake_settings() -> types.SimpleNamespace:
    """Свежий экземпляр fake settings для каждого теста."""
    s = _make_fake_settings()
    _stub_config.settings = s
    _stub_config.get_settings = lambda: s
    return s


@pytest.fixture
def fake_message(fake: Faker):
    """
    Фабрика mock-объектов aiogram.Message.

    Использование:
        def test_something(fake_message):
            msg = fake_message()
            msg = fake_message(user_id=42, text="hi")
    """

    def _factory(
        user_id: int | None = None,
        chat_id: int | None = None,
        text: str | None = None,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str = "ru",
        is_bot: bool = False,
    ) -> MagicMock:
        msg = MagicMock(name="Message")

        msg.from_user = MagicMock(name="User")
        msg.from_user.id = user_id or fake.random_int(min=100_000, max=999_999_999)
        msg.from_user.is_bot = is_bot
        msg.from_user.username = username or fake.user_name()
        msg.from_user.first_name = first_name or fake.first_name()
        msg.from_user.last_name = last_name or fake.last_name()
        msg.from_user.language_code = language_code
        msg.from_user.full_name = f"{msg.from_user.first_name} {msg.from_user.last_name}"

        msg.chat = MagicMock(name="Chat")
        msg.chat.id = chat_id or msg.from_user.id
        msg.chat.type = "private"

        msg.message_id = fake.random_int(min=1, max=9_999_999)
        msg.text = text or fake.sentence()
        msg.caption = None
        msg.photo = None
        msg.voice = None
        msg.document = None

        msg.answer = AsyncMock()
        msg.reply = AsyncMock()
        msg.answer_photo = AsyncMock()
        msg.answer_voice = AsyncMock()
        msg.answer_document = AsyncMock()
        msg.delete = AsyncMock()
        msg.edit_text = AsyncMock()
        msg.edit_reply_markup = AsyncMock()

        msg.bot = MagicMock(name="Bot")
        msg.bot.send_message = AsyncMock()
        msg.bot.send_photo = AsyncMock()
        msg.bot.delete_message = AsyncMock()

        return msg

    return _factory


@pytest.fixture
def fake_callback(fake: Faker):
    """
    Фабрика mock-объектов aiogram.CallbackQuery.

    Использование:
        def test_something(fake_callback):
            cb = fake_callback(data="menu:main")
    """

    def _factory(
        user_id: int | None = None,
        data: str = "test:callback",
        username: str | None = None,
        language_code: str = "ru",
        message_text: str | None = None,
    ) -> MagicMock:
        cb = MagicMock(name="CallbackQuery")

        cb.from_user = MagicMock(name="User")
        cb.from_user.id = user_id or fake.random_int(min=100_000, max=999_999_999)
        cb.from_user.is_bot = False
        cb.from_user.username = username or fake.user_name()
        cb.from_user.first_name = fake.first_name()
        cb.from_user.last_name = fake.last_name()
        cb.from_user.language_code = language_code
        cb.from_user.full_name = f"{cb.from_user.first_name} {cb.from_user.last_name}"

        cb.data = data
        cb.id = str(fake.random_int(min=10**17, max=10**18 - 1))

        cb.message = MagicMock(spec=Message, name="Message")
        cb.message.chat = MagicMock()
        cb.message.chat.id = cb.from_user.id
        cb.message.chat.type = "private"
        cb.message.message_id = fake.random_int(min=1, max=9_999_999)
        cb.message.text = message_text or fake.sentence()
        cb.message.edit_text = AsyncMock()
        cb.message.edit_reply_markup = AsyncMock()
        cb.message.delete = AsyncMock()
        cb.message.answer = AsyncMock()

        cb.answer = AsyncMock()

        cb.bot = MagicMock(name="Bot")
        cb.bot.send_message = AsyncMock()

        return cb

    return _factory


@pytest.fixture
def mock_api_client(mocker):
    """Мок bot/src/services/api_client."""
    return mocker.patch("src.services.api_client")
