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

    @pytest.mark.asyncio
    async def test_user_not_found_returns_early(self) -> None:
        from db.repositories.dialogs import update_n_used_tokens
        session = _make_session()
        session.execute.return_value = _scalar_result(None)
        await update_n_used_tokens(session, _uid(), "gpt-4o", 10, 5)
        session.commit.assert_not_awaited()


# ── start_new_dialog ──────────────────────────────────────────────────────────


class TestStartNewDialog:

    @pytest.mark.asyncio
    async def test_raises_when_user_not_found(self) -> None:
        from db.repositories.dialogs import start_new_dialog
        session = _make_session()
        session.execute.return_value = _scalar_result(None)
        with pytest.raises(ValueError, match="not found"):
            await start_new_dialog(session, _uid())

    @pytest.mark.asyncio
    async def test_creates_dialog_and_commits(self) -> None:
        from db.repositories.dialogs import start_new_dialog
        uid = _uid()
        user = _fake_user_obj(uid)
        user.current_dialog_ids = {}
        user.current_chat_mode = "assistant"
        user.current_model = "gpt-4o"
        session = _make_session()
        session.execute.return_value = _scalar_result(user)
        dialog_id = await start_new_dialog(session, uid)
        assert isinstance(dialog_id, str)
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_commit_false_skips_commit(self) -> None:
        from db.repositories.dialogs import start_new_dialog
        uid = _uid()
        user = _fake_user_obj(uid)
        user.current_dialog_ids = {}
        user.current_chat_mode = "artist"
        user.current_model = "gpt-image-1.5"
        session = _make_session()
        session.execute.return_value = _scalar_result(user)
        await start_new_dialog(session, uid, commit=False)
        session.commit.assert_not_awaited()


# ── get_dialog_messages ───────────────────────────────────────────────────────


class TestGetDialogMessages:

    @pytest.mark.asyncio
    async def test_returns_messages_by_dialog_id(self) -> None:
        from db.repositories.dialogs import get_dialog_messages
        uid = _uid()
        did = _did()
        msgs = [{"user": fake.sentence(), "bot": fake.sentence()}]
        dialog = _fake_dialog_obj(uid=uid, did=did, messages=msgs)
        session = _make_session()
        session.execute.return_value = _scalar_result(dialog)
        result = await get_dialog_messages(session, uid, dialog_id=did)
        assert result == msgs

    @pytest.mark.asyncio
    async def test_no_dialog_id_uses_current_dialog(self) -> None:
        from db.repositories.dialogs import get_dialog_messages
        uid = _uid()
        did = _did()
        user = _fake_user_obj(uid)
        user.current_dialog_id = did
        msgs = [{"user": "hi", "bot": "hello"}]
        dialog = _fake_dialog_obj(uid=uid, did=did, messages=msgs)
        session = _make_session()
        session.execute.side_effect = [
            _scalar_result(user),
            _scalar_result(dialog),
        ]
        result = await get_dialog_messages(session, uid, dialog_id=None)
        assert result == msgs

    @pytest.mark.asyncio
    async def test_no_dialog_returns_empty_list(self) -> None:
        from db.repositories.dialogs import get_dialog_messages
        session = _make_session()
        session.execute.return_value = _scalar_result(None)
        result = await get_dialog_messages(session, _uid(), dialog_id=_did())
        assert result == []

    @pytest.mark.asyncio
    async def test_no_dialog_id_user_not_found_raises(self) -> None:
        from db.repositories.dialogs import get_dialog_messages
        session = _make_session()
        session.execute.return_value = _scalar_result(None)
        with pytest.raises(ValueError, match="not found"):
            await get_dialog_messages(session, _uid(), dialog_id=None)


# ── get_dialog_messages_page ──────────────────────────────────────────────────


class TestGetDialogMessagesPage:

    @pytest.mark.asyncio
    async def test_no_dialog_returns_empty(self) -> None:
        from db.repositories.dialogs import get_dialog_messages_page
        session = _make_session()
        session.execute.return_value = _scalar_result(None)
        msgs, total, cursor = await get_dialog_messages_page(
            session, _uid(), _did(), limit=10
        )
        assert msgs == []
        assert total == 0
        assert cursor == 0

    @pytest.mark.asyncio
    async def test_empty_messages_returns_empty(self) -> None:
        from db.repositories.dialogs import get_dialog_messages_page
        dialog = _fake_dialog_obj(messages=[])
        session = _make_session()
        session.execute.return_value = _scalar_result(dialog)
        msgs, total, cursor = await get_dialog_messages_page(
            session, _uid(), _did(), limit=10
        )
        assert msgs == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_before_index_none_returns_last_n(self) -> None:
        from db.repositories.dialogs import get_dialog_messages_page
        all_msgs = [{"user": str(i), "bot": str(i)} for i in range(20)]
        dialog = _fake_dialog_obj(messages=all_msgs)
        session = _make_session()
        session.execute.return_value = _scalar_result(dialog)
        msgs, total, cursor = await get_dialog_messages_page(
            session, _uid(), _did(), limit=5, before_index=None
        )
        assert len(msgs) == 5
        assert total == 20
        assert msgs == all_msgs[15:20]

    @pytest.mark.asyncio
    async def test_before_index_returns_older_messages(self) -> None:
        from db.repositories.dialogs import get_dialog_messages_page
        all_msgs = [{"user": str(i), "bot": str(i)} for i in range(20)]
        dialog = _fake_dialog_obj(messages=all_msgs)
        session = _make_session()
        session.execute.return_value = _scalar_result(dialog)
        msgs, total, cursor = await get_dialog_messages_page(
            session, _uid(), _did(), limit=5, before_index=10
        )
        assert len(msgs) == 5
        assert msgs == all_msgs[5:10]
        assert cursor == 5

    @pytest.mark.asyncio
    async def test_cursor_zero_when_no_more_messages(self) -> None:
        from db.repositories.dialogs import get_dialog_messages_page
        all_msgs = [{"user": str(i), "bot": str(i)} for i in range(3)]
        dialog = _fake_dialog_obj(messages=all_msgs)
        session = _make_session()
        session.execute.return_value = _scalar_result(dialog)
        msgs, total, cursor = await get_dialog_messages_page(
            session, _uid(), _did(), limit=5, before_index=None
        )
        assert len(msgs) == 3
        assert cursor == 0

    @pytest.mark.asyncio
    async def test_faker_various_page_sizes(self) -> None:
        from db.repositories.dialogs import get_dialog_messages_page
        for limit in [1, 5, 20]:
            n = fake.random_int(min=limit + 1, max=limit + 10)
            all_msgs = [{"user": str(i), "bot": str(i)} for i in range(n)]
            dialog = _fake_dialog_obj(messages=all_msgs)
            session = _make_session()
            session.execute.return_value = _scalar_result(dialog)
            msgs, total, _ = await get_dialog_messages_page(
                session, _uid(), _did(), limit=limit
            )
            assert len(msgs) <= limit
            assert total == n


# ── append_dialog_message ─────────────────────────────────────────────────────


class TestAppendDialogMessage:

    @pytest.mark.asyncio
    async def test_appends_message_and_commits(self) -> None:
        from db.repositories.dialogs import append_dialog_message
        uid = _uid()
        did = _did()
        existing = [{"user": "old", "bot": "reply"}]
        dialog = _fake_dialog_obj(uid=uid, did=did, messages=existing)
        session = _make_session()
        session.execute.return_value = _scalar_result(dialog)
        new_msg = {"user": fake.sentence(), "bot": fake.sentence()}
        await append_dialog_message(session, uid, new_msg, did)
        assert len(dialog.messages) == 2
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_trims_to_max_messages(self) -> None:
        from db.repositories.dialogs import append_dialog_message
        uid = _uid()
        did = _did()
        existing = [{"user": str(i), "bot": str(i)} for i in range(5)]
        dialog = _fake_dialog_obj(uid=uid, did=did, messages=existing)
        session = _make_session()
        session.execute.return_value = _scalar_result(dialog)
        await append_dialog_message(session, uid, {"user": "new", "bot": "r"}, did, max_messages=3)
        assert len(dialog.messages) == 3

    @pytest.mark.asyncio
    async def test_no_dialog_found_only_commits(self) -> None:
        from db.repositories.dialogs import append_dialog_message
        session = _make_session()
        session.execute.return_value = _scalar_result(None)
        await append_dialog_message(session, _uid(), {"user": "x", "bot": "y"}, _did())
        session.commit.assert_awaited_once()


# ── ensure_active_dialog ──────────────────────────────────────────────────────


class TestEnsureActiveDialog:

    @pytest.mark.asyncio
    async def test_user_not_found_raises(self) -> None:
        from db.repositories.dialogs import ensure_active_dialog
        session = _make_session()
        session.execute.return_value = _scalar_result(None)
        with pytest.raises(ValueError, match="not found"):
            await ensure_active_dialog(session, _uid())

    @pytest.mark.asyncio
    async def test_creates_new_dialog_when_none_exists(self) -> None:
        from db.repositories.dialogs import ensure_active_dialog
        uid = _uid()
        user = _fake_user_obj(uid)
        user.current_dialog_ids = {}
        user.current_dialog_id = None
        user.current_chat_mode = "assistant"
        user.current_model = "gpt-4o"
        session = _make_session()
        session.execute.return_value = _scalar_result(user)
        dialog_id = await ensure_active_dialog(session, uid)
        assert isinstance(dialog_id, str)
        session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_reuses_existing_valid_dialog(self) -> None:
        from db.repositories.dialogs import ensure_active_dialog
        uid = _uid()
        did = _did()
        user = _fake_user_obj(uid)
        user.current_dialog_ids = {"assistant": did}
        user.current_dialog_id = did
        user.current_chat_mode = "assistant"
        session = _make_session()
        existing_dialog_result = MagicMock()
        existing_dialog_result.scalar_one_or_none.return_value = did
        session.execute.side_effect = [
            _scalar_result(user),
            existing_dialog_result,
        ]
        result = await ensure_active_dialog(session, uid)
        assert result == did

    @pytest.mark.asyncio
    async def test_updates_current_dialog_id_when_out_of_sync(self) -> None:
        from db.repositories.dialogs import ensure_active_dialog
        uid = _uid()
        did = _did()
        user = _fake_user_obj(uid)
        user.current_dialog_ids = {"assistant": did}
        user.current_dialog_id = "old_different_id"
        user.current_chat_mode = "assistant"
        session = _make_session()
        existing_dialog_result = MagicMock()
        existing_dialog_result.scalar_one_or_none.return_value = did
        session.execute.side_effect = [
            _scalar_result(user),
            existing_dialog_result,
        ]
        result = await ensure_active_dialog(session, uid)
        assert result == did
        assert user.current_dialog_id == did
        session.commit.assert_awaited()


# ── ensure_active_mini_app_dialog ─────────────────────────────────────────────


class TestEnsureActiveMiniAppDialog:

    @pytest.mark.asyncio
    async def test_user_not_found_raises(self) -> None:
        from db.repositories.dialogs import ensure_active_mini_app_dialog
        session = _make_session()
        session.execute.return_value = _scalar_result(None)
        with pytest.raises(ValueError, match="not found"):
            await ensure_active_mini_app_dialog(session, _uid())

    @pytest.mark.asyncio
    async def test_reuses_existing_valid_dialog(self) -> None:
        from db.repositories.dialogs import ensure_active_mini_app_dialog
        uid = _uid()
        did = _did()
        user = _fake_user_obj(uid)
        user.mini_app_chat_mode = "assistant"
        user.mini_app_dialog_ids = {"assistant": did}
        user.current_model = "gpt-4o"
        session = _make_session()
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = did
        session.execute.side_effect = [
            _scalar_result(user),
            existing_result,
        ]
        result = await ensure_active_mini_app_dialog(session, uid)
        assert result == did

    @pytest.mark.asyncio
    async def test_creates_new_when_no_existing_dialog(self) -> None:
        from db.repositories.dialogs import ensure_active_mini_app_dialog
        uid = _uid()
        user = _fake_user_obj(uid)
        user.mini_app_chat_mode = "assistant"
        user.mini_app_dialog_ids = {}
        user.current_model = "gpt-4o"
        session = _make_session()
        session.execute.return_value = _scalar_result(user)
        result = await ensure_active_mini_app_dialog(session, uid)
        assert isinstance(result, str)
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_new_when_existing_not_found_in_db(self) -> None:
        from db.repositories.dialogs import ensure_active_mini_app_dialog
        uid = _uid()
        did = _did()
        user = _fake_user_obj(uid)
        user.mini_app_chat_mode = "artist"
        user.mini_app_dialog_ids = {"artist": did}
        user.current_model = "gpt-image-1.5"
        session = _make_session()
        missing_result = MagicMock()
        missing_result.scalar_one_or_none.return_value = None
        session.execute.side_effect = [
            _scalar_result(user),
            missing_result,
        ]
        result = await ensure_active_mini_app_dialog(session, uid)
        assert isinstance(result, str)
        session.add.assert_called_once()
