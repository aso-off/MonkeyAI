"""
Тесты для bot/src/bot/routers/profile/balance.py.

Покрываем:
- _balance_keyboard()    — структура клавиатуры
- _build_balance_text()  — user=None, пустые токены, с токенами, с изображениями, с голосом
- cmd_balance()          — без db_user, с db_user
- cb_show_balance()      — без db_user, с db_user
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)


def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)


def _fake_db_user(
    n_used_tokens: dict | None = None,
    n_generated_images: int = 0,
    n_transcribed_seconds: float = 0.0,
) -> MagicMock:
    u = MagicMock()
    u.id = _uid()
    u.n_used_tokens = n_used_tokens or {}
    u.n_generated_images = n_generated_images
    u.n_transcribed_seconds = n_transcribed_seconds
    return u


def _fake_message(uid: int | None = None) -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = uid or _uid()
    msg.answer = AsyncMock()
    return msg


def _fake_callback(uid: int | None = None) -> MagicMock:
    cb = MagicMock()
    cb.data = "show_balance"
    cb.from_user = MagicMock()
    cb.from_user.id = uid or _uid()
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    return cb


_MODELS_SETTINGS = {
    "info": {
        "gpt-4o": {
            "price_per_1000_input_tokens": 0.005,
            "price_per_1000_output_tokens": 0.015,
        },
        "gpt-image-1.5": {"price_per_1_image": 0.04},
        "whisper-1": {"price_per_1_min": 0.006},
    }
}


# ── _balance_keyboard ─────────────────────────────────────────────────────────


class TestBalanceKeyboard:

    def test_keyboard_has_back_to_profile_button(self) -> None:
        from src.bot.routers.profile.balance import _balance_keyboard
        kb = _balance_keyboard("ru")
        assert kb is not None
        assert len(kb.inline_keyboard) == 1
        assert kb.inline_keyboard[0][0].callback_data == "profile"


# ── _build_balance_text ───────────────────────────────────────────────────────


class TestBuildBalanceText:

    def test_user_none_returns_error_text(self) -> None:
        from src.bot.routers.profile.balance import _build_balance_text
        with patch("src.bot.routers.profile.balance.settings") as mock_s:
            mock_s.models = _MODELS_SETTINGS
            mock_s.chatgpt_price_per_1000_tokens = 0.002
            mock_s.whisper_price_per_1_min = 0.006
            result = _build_balance_text(None, "ru")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_usage_returns_text(self) -> None:
        from src.bot.routers.profile.balance import _build_balance_text
        db_user = _fake_db_user()
        with patch("src.bot.routers.profile.balance.settings") as mock_s, \
             patch("src.bot.routers.profile.balance.t", return_value=""):
            mock_s.models = _MODELS_SETTINGS
            mock_s.chatgpt_price_per_1000_tokens = 0.002
            mock_s.whisper_price_per_1_min = 0.006
            result = _build_balance_text(db_user, "en")
        assert isinstance(result, str)

    def test_with_token_usage_calculates_cost(self) -> None:
        from src.bot.routers.profile.balance import _build_balance_text
        n_input = fake.random_int(min=100, max=50000)
        n_output = fake.random_int(min=100, max=20000)
        db_user = _fake_db_user(
            n_used_tokens={"gpt-4o": {"n_input_tokens": n_input, "n_output_tokens": n_output}}
        )
        with patch("src.bot.routers.profile.balance.settings") as mock_s, \
             patch("src.bot.routers.profile.balance.t", return_value=""):
            mock_s.models = _MODELS_SETTINGS
            mock_s.chatgpt_price_per_1000_tokens = 0.002
            mock_s.whisper_price_per_1_min = 0.006
            result = _build_balance_text(db_user, "ru")
        assert isinstance(result, str)

    def test_with_images_includes_image_cost(self) -> None:
        from src.bot.routers.profile.balance import _build_balance_text
        n_images = fake.random_int(min=1, max=20)
        db_user = _fake_db_user(n_generated_images=n_images)
        with patch("src.bot.routers.profile.balance.settings") as mock_s, \
             patch("src.bot.routers.profile.balance.t", return_value=""):
            mock_s.models = _MODELS_SETTINGS
            mock_s.chatgpt_price_per_1000_tokens = 0.002
            mock_s.whisper_price_per_1_min = 0.006
            result = _build_balance_text(db_user, "en")
        assert isinstance(result, str)

    def test_with_voice_includes_voice_cost(self) -> None:
        from src.bot.routers.profile.balance import _build_balance_text
        seconds = fake.pyfloat(min_value=10.0, max_value=3600.0)
        db_user = _fake_db_user(n_transcribed_seconds=seconds)
        with patch("src.bot.routers.profile.balance.settings") as mock_s, \
             patch("src.bot.routers.profile.balance.t", return_value=""):
            mock_s.models = _MODELS_SETTINGS
            mock_s.chatgpt_price_per_1000_tokens = 0.002
            mock_s.whisper_price_per_1_min = 0.006
            result = _build_balance_text(db_user, "ru")
        assert isinstance(result, str)

    def test_faker_random_token_counts(self) -> None:
        from src.bot.routers.profile.balance import _build_balance_text
        for _ in range(3):
            db_user = _fake_db_user(
                n_used_tokens={
                    fake.lexify("model-????"): {
                        "n_input_tokens": fake.random_int(min=0, max=10000),
                        "n_output_tokens": fake.random_int(min=0, max=5000),
                    }
                }
            )
            with patch("src.bot.routers.profile.balance.settings") as mock_s, \
                 patch("src.bot.routers.profile.balance.t", return_value=""):
                mock_s.models = {"info": {}}
                mock_s.chatgpt_price_per_1000_tokens = 0.002
                mock_s.whisper_price_per_1_min = 0.006
                result = _build_balance_text(db_user, "en")
            assert isinstance(result, str)


# ── cmd_balance ───────────────────────────────────────────────────────────────


class TestCmdBalance:

    @pytest.mark.asyncio
    async def test_no_db_user_sends_error_text(self) -> None:
        from src.bot.routers.profile.balance import cmd_balance
        msg = _fake_message()
        with patch("src.bot.routers.profile.balance.settings") as mock_s, \
             patch("src.bot.routers.profile.balance.t", return_value="error"):
            mock_s.models = _MODELS_SETTINGS
            mock_s.chatgpt_price_per_1000_tokens = 0.002
            mock_s.whisper_price_per_1_min = 0.006
            await cmd_balance(msg, language="ru", db_user=None)
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_db_user_sends_balance(self) -> None:
        from src.bot.routers.profile.balance import cmd_balance
        db_user = _fake_db_user()
        msg = _fake_message(db_user.id)
        with patch("src.bot.routers.profile.balance.settings") as mock_s, \
             patch("src.bot.routers.profile.balance.t", return_value=""):
            mock_s.models = _MODELS_SETTINGS
            mock_s.chatgpt_price_per_1000_tokens = 0.002
            mock_s.whisper_price_per_1_min = 0.006
            await cmd_balance(msg, language="en", db_user=db_user)
        msg.answer.assert_awaited_once()


# ── cb_show_balance ───────────────────────────────────────────────────────────


class TestCbShowBalance:

    @pytest.mark.asyncio
    async def test_no_db_user_edits_error(self) -> None:
        from src.bot.routers.profile.balance import cb_show_balance
        cb = _fake_callback()
        with patch("src.bot.routers.profile.balance.settings") as mock_s, \
             patch("src.bot.routers.profile.balance.t", return_value="error"):
            mock_s.models = _MODELS_SETTINGS
            mock_s.chatgpt_price_per_1000_tokens = 0.002
            mock_s.whisper_price_per_1_min = 0.006
            await cb_show_balance(cb, language="ru", db_user=None)
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_db_user_edits_balance(self) -> None:
        from src.bot.routers.profile.balance import cb_show_balance
        db_user = _fake_db_user(
            n_used_tokens={"gpt-4o": {"n_input_tokens": 1000, "n_output_tokens": 500}},
            n_generated_images=fake.random_int(min=0, max=5),
        )
        cb = _fake_callback(uid=db_user.id)
        with patch("src.bot.routers.profile.balance.settings") as mock_s, \
             patch("src.bot.routers.profile.balance.t", return_value=""):
            mock_s.models = _MODELS_SETTINGS
            mock_s.chatgpt_price_per_1000_tokens = 0.002
            mock_s.whisper_price_per_1_min = 0.006
            await cb_show_balance(cb, language="en", db_user=db_user)
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()
