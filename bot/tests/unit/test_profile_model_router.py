"""
Тесты для bot/src/bot/routers/profile/model.py.

Покрываем:
- _model_keyboard()   — пустые модели, с моделями, текущая модель отмечена ✅
- _model_text()       — со scores, без scores
- cmd_model()         — db_user=None, модель в списке, модель не в списке
- cb_profile_model()  — те же ветки через callback
- cb_set_model()      — модель недоступна, db_user=None, та же модель, смена модели
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)


def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)


def _fake_db_user(model: str = "gpt-4o") -> MagicMock:
    u = MagicMock()
    u.id = _uid()
    u.current_model = model
    u.current_chat_mode = "assistant"
    return u


def _fake_models_settings(available: list[str] | None = None) -> dict:
    avail = available or ["gpt-4o", "gpt-5"]
    return {
        "available_text_models": avail,
        "info": {
            k: {
                "name": k.upper(),
                "scores": {"quality": fake.random_int(min=1, max=5)},
            }
            for k in avail
        },
    }


def _fake_message(uid: int | None = None) -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = uid or _uid()
    msg.answer = AsyncMock()
    return msg


def _fake_callback(data: str = "profile_model", uid: int | None = None) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user = MagicMock()
    cb.from_user.id = uid or _uid()
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    return cb


# ── _model_keyboard ───────────────────────────────────────────────────────────


class TestModelKeyboard:

    def test_empty_models_returns_keyboard_with_only_back_button(self) -> None:
        from src.bot.routers.profile.model import _model_keyboard
        with patch("src.bot.routers.profile.model.settings") as mock_s:
            mock_s.models = {"available_text_models": [], "info": {}}
            kb = _model_keyboard("ru", "gpt-4o")
        assert kb is not None
        # Только кнопка "назад"
        assert len(kb.inline_keyboard) == 1

    def test_with_models_returns_row_per_model_plus_back(self) -> None:
        from src.bot.routers.profile.model import _model_keyboard
        models = _fake_models_settings(["gpt-4o", "gpt-5", "gpt-5.4-mini"])
        with patch("src.bot.routers.profile.model.settings") as mock_s:
            mock_s.models = models
            kb = _model_keyboard("en", "gpt-4o")
        # 3 модели + 1 кнопка назад
        assert len(kb.inline_keyboard) == 4

    def test_current_model_has_checkmark(self) -> None:
        from src.bot.routers.profile.model import _model_keyboard
        models = _fake_models_settings(["gpt-4o", "gpt-5"])
        with patch("src.bot.routers.profile.model.settings") as mock_s:
            mock_s.models = models
            kb = _model_keyboard("ru", "gpt-4o")
        labels = [btn.text for row in kb.inline_keyboard for btn in row]
        gpt4o_label = next(l for l in labels if "GPT-4O" in l)
        assert "✅" in gpt4o_label
        gpt5_label = next(l for l in labels if "GPT-5" in l and "MINI" not in l)
        assert "✅" not in gpt5_label

    def test_unknown_model_in_info_skipped(self) -> None:
        from src.bot.routers.profile.model import _model_keyboard
        with patch("src.bot.routers.profile.model.settings") as mock_s:
            mock_s.models = {
                "available_text_models": ["known", "unknown"],
                "info": {"known": {"name": "Known"}},
            }
            kb = _model_keyboard("en", "known")
        labels = [btn.text for row in kb.inline_keyboard for btn in row]
        assert not any("unknown" in l.lower() for l in labels)


# ── _model_text ───────────────────────────────────────────────────────────────


class TestModelText:

    def test_with_scores_builds_star_lines(self) -> None:
        from src.bot.routers.profile.model import _model_text
        with patch("src.bot.routers.profile.model.settings") as mock_s, \
             patch("src.bot.routers.profile.model.t", return_value=""):
            mock_s.models = {
                "info": {
                    "gpt-4o": {
                        "scores": {"quality": 4, "speed": 3},
                    }
                }
            }
            text = _model_text("ru", "gpt-4o")
        assert "🟢" in text

    def test_without_scores_returns_text_without_stars(self) -> None:
        from src.bot.routers.profile.model import _model_text
        with patch("src.bot.routers.profile.model.settings") as mock_s, \
             patch("src.bot.routers.profile.model.t", return_value=""):
            mock_s.models = {"info": {"gpt-4o": {}}}
            text = _model_text("ru", "gpt-4o")
        assert "🟢" not in text


# ── cmd_model ─────────────────────────────────────────────────────────────────


class TestCmdModel:

    @pytest.mark.asyncio
    async def test_db_user_none_sends_error(self) -> None:
        from src.bot.routers.profile.model import cmd_model
        msg = _fake_message()
        with patch("src.bot.routers.profile.model.settings") as mock_s:
            mock_s.models = _fake_models_settings()
            await cmd_model(msg, language="ru", db_user=None)
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_model_in_available_sends_keyboard(self) -> None:
        from src.bot.routers.profile.model import cmd_model
        models = _fake_models_settings(["gpt-4o", "gpt-5"])
        db_user = _fake_db_user("gpt-4o")
        msg = _fake_message(db_user.id)
        with patch("src.bot.routers.profile.model.settings") as mock_s, \
             patch("src.bot.routers.profile.model.api") as mock_api:
            mock_s.models = models
            await cmd_model(msg, language="en", db_user=db_user)
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_model_not_in_available_resets_to_first(self) -> None:
        from src.bot.routers.profile.model import cmd_model
        models = _fake_models_settings(["gpt-5", "gpt-5.4-mini"])
        db_user = _fake_db_user("old-model")
        msg = _fake_message(db_user.id)
        with patch("src.bot.routers.profile.model.settings") as mock_s, \
             patch("src.bot.routers.profile.model.api") as mock_api:
            mock_s.models = models
            mock_api.update_user = AsyncMock()
            await cmd_model(msg, language="en", db_user=db_user)
        mock_api.update_user.assert_awaited_once()
        msg.answer.assert_awaited_once()


# ── cb_profile_model ──────────────────────────────────────────────────────────


class TestCbProfileModel:

    @pytest.mark.asyncio
    async def test_db_user_none_edits_error(self) -> None:
        from src.bot.routers.profile.model import cb_profile_model
        cb = _fake_callback()
        with patch("src.bot.routers.profile.model.settings") as mock_s:
            mock_s.models = _fake_models_settings()
            await cb_profile_model(cb, language="ru", db_user=None)
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_model_in_available_edits_text(self) -> None:
        from src.bot.routers.profile.model import cb_profile_model
        models = _fake_models_settings(["gpt-4o"])
        db_user = _fake_db_user("gpt-4o")
        cb = _fake_callback(uid=db_user.id)
        with patch("src.bot.routers.profile.model.settings") as mock_s, \
             patch("src.bot.routers.profile.model.api"):
            mock_s.models = models
            await cb_profile_model(cb, language="de", db_user=db_user)
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_model_not_in_available_resets_model(self) -> None:
        from src.bot.routers.profile.model import cb_profile_model
        models = _fake_models_settings(["gpt-5"])
        db_user = _fake_db_user("old-model")
        cb = _fake_callback(uid=db_user.id)
        with patch("src.bot.routers.profile.model.settings") as mock_s, \
             patch("src.bot.routers.profile.model.api") as mock_api:
            mock_s.models = models
            mock_api.update_user = AsyncMock()
            await cb_profile_model(cb, language="ru", db_user=db_user)
        mock_api.update_user.assert_awaited_once()


# ── cb_set_model ──────────────────────────────────────────────────────────────


class TestCbSetModel:

    @pytest.mark.asyncio
    async def test_model_not_available_answers_only(self) -> None:
        from src.bot.routers.profile.model import cb_set_model
        cb = _fake_callback(data="set_model|nonexistent")
        with patch("src.bot.routers.profile.model.settings") as mock_s, \
             patch("src.bot.routers.profile.model.api") as mock_api:
            mock_s.models = _fake_models_settings(["gpt-4o"])
            await cb_set_model(cb, language="ru", db_user=MagicMock())
        cb.answer.assert_awaited_once()
        mock_api.update_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_user_none_answers_only(self) -> None:
        from src.bot.routers.profile.model import cb_set_model
        cb = _fake_callback(data="set_model|gpt-4o")
        with patch("src.bot.routers.profile.model.settings") as mock_s, \
             patch("src.bot.routers.profile.model.api") as mock_api:
            mock_s.models = _fake_models_settings(["gpt-4o"])
            await cb_set_model(cb, language="ru", db_user=None)
        cb.answer.assert_awaited()
        mock_api.update_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_same_model_answers_without_update(self) -> None:
        from src.bot.routers.profile.model import cb_set_model
        model = "gpt-4o"
        cb = _fake_callback(data=f"set_model|{model}")
        db_user = _fake_db_user(model)
        with patch("src.bot.routers.profile.model.settings") as mock_s, \
             patch("src.bot.routers.profile.model.api") as mock_api:
            mock_s.models = _fake_models_settings([model])
            await cb_set_model(cb, language="en", db_user=db_user)
        mock_api.update_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_different_model_updates_and_refreshes(self) -> None:
        from src.bot.routers.profile.model import cb_set_model
        new_model = "gpt-5"
        cb = _fake_callback(data=f"set_model|{new_model}")
        db_user = _fake_db_user("gpt-4o")
        with patch("src.bot.routers.profile.model.settings") as mock_s, \
             patch("src.bot.routers.profile.model.api") as mock_api:
            mock_s.models = _fake_models_settings(["gpt-4o", "gpt-5"])
            mock_api.update_user = AsyncMock()
            mock_api.start_new_dialog = AsyncMock()
            await cb_set_model(cb, language="en", db_user=db_user)
        mock_api.update_user.assert_awaited_once()
        mock_api.start_new_dialog.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_faker_various_model_names(self) -> None:
        from src.bot.routers.profile.model import cb_set_model
        for _ in range(3):
            model = fake.lexify("model-????")
            cb = _fake_callback(data=f"set_model|{model}")
            with patch("src.bot.routers.profile.model.settings") as mock_s, \
                 patch("src.bot.routers.profile.model.api"):
                mock_s.models = {"available_text_models": [], "info": {}}
                await cb_set_model(cb, language="ru", db_user=MagicMock())
            cb.answer.assert_awaited()
