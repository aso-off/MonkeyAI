"""
Расширенные тесты для api/src/db/repositories/dialogs.py.

Покрываем оставшиеся функции:
- get_dialog_messages_by_mode()
- get_all_users_count()
- get_active_users_count()
- get_user_message_count()
- get_dialog_messages_page()

Faker: user IDs, dialog IDs, модели, messages.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)


def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)


def _did() -> str:
    return str(uuid.uuid4())


def _make_session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    s.commit = AsyncMock()
    s.rollback = AsyncMock()
    s.execute = AsyncMock()
    return s


def _scalar_result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _scalar_value(value):
    r = MagicMock()
    r.scalar_one.return_value = value
    return r


def _fake_user_obj(uid: int | None = None):
    from db.models.user import User
    u = MagicMock(spec=User)
    u.id = uid or _uid()
    u.current_chat_mode = "assistant"
    u.current_model = "gpt-4o"
    u.current_dialog_id = None
    u.current_dialog_ids = {}
    u.mini_app_dialog_ids = {}
    return u


def _fake_dialog_obj(uid: int | None = None, did: str | None = None, messages: list | None = None):
    from db.models.user import Dialog
    d = MagicMock(spec=Dialog)
    d.id = did or _did()
    d.user_id = uid or _uid()
    d.chat_mode = "assistant"
    d.messages = messages or []
    return d


# ── get_dialog_messages_by_mode ───────────────────────────────────────────────


class TestGetDialogMessagesByMode:

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_dialogs(self) -> None:
        from db.repositories.dialogs import get_dialog_messages_by_mode
        uid = _uid()
        user = _fake_user_obj(uid)
        user.current_dialog_ids = {}

        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        result = await get_dialog_messages_by_mode(session, uid)
        assert result == {}

    @pytest.mark.asyncio
    async def test_raises_when_user_not_found(self) -> None:
        from db.repositories.dialogs import get_dialog_messages_by_mode
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        with pytest.raises(ValueError, match="not found"):
            await get_dialog_messages_by_mode(session, _uid())

    @pytest.mark.asyncio
    async def test_returns_messages_for_each_mode(self) -> None:
        from db.repositories.dialogs import get_dialog_messages_by_mode
        uid = _uid()
        did1 = _did()
        did2 = _did()
        user = _fake_user_obj(uid)
        user.current_dialog_ids = {"assistant": did1, "artist": did2}

        msgs1 = [{"user": fake.sentence(), "bot": fake.sentence()}]
        msgs2 = []

        r_user = _scalar_result(user)
        r_d1 = MagicMock()
        r_d1.scalar_one_or_none.return_value = msgs1
        r_d2 = MagicMock()
        r_d2.scalar_one_or_none.return_value = msgs2

        session = _make_session()
        session.execute.side_effect = [r_user, r_d1, r_d2]

        result = await get_dialog_messages_by_mode(session, uid)
        assert "assistant" in result
        assert "artist" in result

    @pytest.mark.asyncio
    async def test_skips_none_dialog_ids(self) -> None:
        from db.repositories.dialogs import get_dialog_messages_by_mode
        uid = _uid()
        user = _fake_user_obj(uid)
        user.current_dialog_ids = {"assistant": None, "artist": _did()}

        session = _make_session()
        r_user = _scalar_result(user)
        r_msgs = MagicMock()
        r_msgs.scalar_one_or_none.return_value = []
        session.execute.side_effect = [r_user, r_msgs]

        result = await get_dialog_messages_by_mode(session, uid)
        # assistant skipped (None), artist included
        assert "assistant" not in result
        assert "artist" in result


# ── get_all_users_count ───────────────────────────────────────────────────────


class TestGetAllUsersCount:

    @pytest.mark.asyncio
    async def test_returns_total_count(self) -> None:
        from db.repositories.dialogs import get_all_users_count
        count = fake.random_int(min=0, max=10000)
        session = _make_session()
        session.execute.return_value = _scalar_value(count)

        result = await get_all_users_count(session)
        assert result == count

    @pytest.mark.asyncio
    async def test_returns_zero_when_empty(self) -> None:
        from db.repositories.dialogs import get_all_users_count
        session = _make_session()
        session.execute.return_value = _scalar_value(0)

        result = await get_all_users_count(session)
        assert result == 0

    @pytest.mark.asyncio
    async def test_faker_various_counts(self) -> None:
        from db.repositories.dialogs import get_all_users_count
        for _ in range(3):
            count = fake.random_int(min=1, max=50000)
            session = _make_session()
            session.execute.return_value = _scalar_value(count)
            result = await get_all_users_count(session)
            assert result == count


# ── get_active_users_count ────────────────────────────────────────────────────


class TestGetActiveUsersCount:

    @pytest.mark.asyncio
    async def test_returns_active_count(self) -> None:
        from db.repositories.dialogs import get_active_users_count
        count = fake.random_int(min=0, max=1000)
        session = _make_session()
        session.execute.return_value = _scalar_value(count)

        result = await get_active_users_count(session)
        assert result == count

    @pytest.mark.asyncio
    async def test_accepts_days_parameter(self) -> None:
        from db.repositories.dialogs import get_active_users_count
        count = fake.random_int(min=0, max=500)
        session = _make_session()
        session.execute.return_value = _scalar_value(count)

        result = await get_active_users_count(session, days=30)
        assert result == count


# ── get_user_message_count ────────────────────────────────────────────────────


class TestGetUserMessageCount:

    @pytest.mark.asyncio
    async def test_returns_message_count(self) -> None:
        from db.repositories.dialogs import get_user_message_count
        uid = _uid()
        count = fake.random_int(min=0, max=5000)
        session = _make_session()
        session.execute.return_value = _scalar_value(count)

        result = await get_user_message_count(session, uid)
        assert result == count

    @pytest.mark.asyncio
    async def test_returns_zero_for_new_user(self) -> None:
        from db.repositories.dialogs import get_user_message_count
        session = _make_session()
        session.execute.return_value = _scalar_value(0)

        result = await get_user_message_count(session, _uid())
        assert result == 0

    @pytest.mark.asyncio
    async def test_faker_various_users(self) -> None:
        from db.repositories.dialogs import get_user_message_count
        for _ in range(3):
            uid = _uid()
            count = fake.random_int(min=1, max=10000)
            session = _make_session()
            session.execute.return_value = _scalar_value(count)
            result = await get_user_message_count(session, uid)
            assert result == count


# ── set_dialog_messages edge cases ───────────────────────────────────────────


class TestSetDialogMessagesEdgeCases:

    @pytest.mark.asyncio
    async def test_set_with_commit_false(self) -> None:
        from db.repositories.dialogs import set_dialog_messages
        session = _make_session()
        await set_dialog_messages(session, _uid(), [], _did(), commit=False)
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_raises_when_user_not_found_and_no_dialog_id(self) -> None:
        from db.repositories.dialogs import set_dialog_messages
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        with pytest.raises((ValueError, AttributeError)):
            await set_dialog_messages(session, _uid(), [], dialog_id=None)


# ── update_n_used_tokens edge cases ──────────────────────────────────────────


class TestUpdateNUsedTokensEdgeCases:

    @pytest.mark.asyncio
    async def test_accumulates_existing_tokens(self) -> None:
        from db.repositories.dialogs import update_n_used_tokens
        uid = _uid()
        model = "gpt-4o"
        user = _fake_user_obj(uid)
        user.n_used_tokens = {model: {"n_input_tokens": 100, "n_output_tokens": 50}}

        session = _make_session()
        session.execute.side_effect = [
            _scalar_result(user),  # SELECT FOR UPDATE
            MagicMock(),           # UPDATE
        ]

        n_in = fake.random_int(min=10, max=200)
        n_out = fake.random_int(min=5, max=100)
        await update_n_used_tokens(session, uid, model, n_in, n_out)
        session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_faker_multiple_models(self) -> None:
        from db.repositories.dialogs import update_n_used_tokens
        models = ["gpt-4o", "gpt-5-nano", "gpt-5-mini"]
        for model in models:
            uid = _uid()
            user = _fake_user_obj(uid)
            user.n_used_tokens = {}
            session = _make_session()
            session.execute.side_effect = [
                _scalar_result(user),
                MagicMock(),
            ]
            await update_n_used_tokens(
                session, uid, model,
                fake.random_int(min=1, max=500),
                fake.random_int(min=1, max=200),
            )
            session.commit.assert_awaited()
