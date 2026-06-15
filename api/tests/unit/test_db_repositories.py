"""
Тесты для api/src/db/repositories/users.py и dialogs.py.

Стратегия: AsyncSession мокируется через AsyncMock; все SQL-результаты
возвращаются через result_mock.scalar_one_or_none().

Faker: user IDs, имена, токены, dialog IDs, модели.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)


# ── Helpers ───────────────────────────────────────────────────────────────────


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


def _scalars_result(values: list):
    r = MagicMock()
    r.scalars.return_value.all.return_value = values
    return r


def _fake_state():
    from db.models.user import UserState
    s = MagicMock(spec=UserState)
    s.current_model = "gpt-4o"
    s.current_chat_mode = "assistant"
    s.current_dialog_id = None
    s.current_dialog_ids = {}
    s.mini_app_dialog_ids = {}
    s.theme = "system"
    s.mini_app_chat_mode = "assistant"
    return s


def _fake_stats():
    from db.models.user import UserStatistics
    st = MagicMock(spec=UserStatistics)
    st.n_used_tokens = {}
    st.n_generated_images = 0
    st.n_transcribed_seconds = 0.0
    return st


def _fake_user_obj(uid: int | None = None):
    from db.models.user import User
    u = MagicMock(spec=User)
    u.id = uid or _uid()
    u.chat_id = u.id
    u.first_name = fake.first_name()
    u.last_name = fake.last_name()
    u.username = fake.user_name()
    u.language = fake.random_element(["ru", "en", "de"])
    u.is_admin = False
    u.is_whitelisted = True
    u.state = _fake_state()
    u.statistics = _fake_stats()
    return u


def _fake_dialog_obj(uid: int | None = None, did: str | None = None):
    from db.models.user import Dialog
    d = MagicMock(spec=Dialog)
    d.id = did or _did()
    d.user_id = uid or _uid()
    d.chat_mode = "assistant"
    d.model = "gpt-4o"
    d.messages = []
    return d


# ═══════════════════════════════════════════════════════════════════
# db/repositories/users.py
# ═══════════════════════════════════════════════════════════════════


class TestGetUser:

    @pytest.mark.asyncio
    async def test_returns_user_when_found(self) -> None:
        from db.repositories.users import get_user
        uid = _uid()
        user = _fake_user_obj(uid)
        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        result = await get_user(session, uid)
        assert result is user

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        from db.repositories.users import get_user
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        result = await get_user(session, _uid())
        assert result is None

    @pytest.mark.asyncio
    async def test_faker_batch_users(self) -> None:
        from db.repositories.users import get_user
        for _ in range(3):
            uid = _uid()
            user = _fake_user_obj(uid)
            session = _make_session()
            session.execute.return_value = _scalar_result(user)
            result = await get_user(session, uid)
            assert result is not None
            assert result.id == uid


class TestIsUserAdmin:

    @pytest.mark.asyncio
    async def test_returns_true_when_db_user_is_admin(self) -> None:
        from db.repositories.users import is_user_admin
        uid = _uid()
        user = _fake_user_obj(uid)
        user.is_admin = True
        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        result = await is_user_admin(session, uid)
        assert result is True

    @pytest.mark.asyncio
    async def test_falls_back_to_settings_admin_ids_when_user_none(self) -> None:
        from db.repositories.users import is_user_admin
        uid = _uid()
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        with patch("db.repositories.users.settings") as mock_settings:
            mock_settings.admin_ids = [uid]
            result = await is_user_admin(session, uid)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_admin(self) -> None:
        from db.repositories.users import is_user_admin
        uid = _uid()
        user = _fake_user_obj(uid)
        user.is_admin = False
        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        result = await is_user_admin(session, uid)
        assert result is False


class TestGetOrCreateUser:

    @pytest.mark.asyncio
    async def test_returns_existing_user_with_false(self) -> None:
        from db.repositories.users import get_or_create_user
        uid = _uid()
        user = _fake_user_obj(uid)
        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        result, created = await get_or_create_user(session, uid, uid)
        assert result is user
        assert created is False

    @pytest.mark.asyncio
    async def test_creates_new_user_returns_true(self) -> None:
        from db.repositories.users import get_or_create_user
        uid = _uid()
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        with patch("db.repositories.users.settings") as mock_settings:
            mock_settings.models.get.return_value = []
            mock_settings.admin_ids = []
            mock_settings.allowed_user_ids = []
            result, created = await get_or_create_user(
                session, uid, uid,
                first_name=fake.first_name(),
                username=fake.user_name(),
            )

        assert created is True
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handles_integrity_error_on_race(self) -> None:
        from db.repositories.users import get_or_create_user
        from sqlalchemy.exc import IntegrityError
        uid = _uid()
        existing_user = _fake_user_obj(uid)

        call_count = [0]
        async def _execute(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return _scalar_result(None)  # first get_user → None
            return _scalar_result(existing_user)  # second get_user after rollback

        session = _make_session()
        session.execute.side_effect = _execute
        session.commit = AsyncMock(side_effect=IntegrityError("", {}, Exception("dup")))

        with patch("db.repositories.users.settings") as mock_settings:
            mock_settings.models.get.return_value = []
            mock_settings.admin_ids = []
            mock_settings.allowed_user_ids = []
            result, created = await get_or_create_user(session, uid, uid)

        assert created is False


class TestUpdateUser:

    @pytest.mark.asyncio
    async def test_executes_update_and_commits(self) -> None:
        from db.repositories.users import update_user
        uid = _uid()
        session = _make_session()

        await update_user(session, uid, language="en", theme="dark")

        # language → users, theme → user_states: два UPDATE, один commit
        assert session.execute.await_count == 2
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_faker_multiple_field_updates(self) -> None:
        from db.repositories.users import update_user
        for _ in range(3):
            uid = _uid()
            session = _make_session()
            lang = fake.random_element(["ru", "en", "de"])
            await update_user(session, uid, language=lang)
            session.commit.assert_awaited_once()


class TestUpdateLastInteraction:

    @pytest.mark.asyncio
    async def test_updates_last_interaction_and_commits(self) -> None:
        from db.repositories.users import update_last_interaction
        uid = _uid()
        session = _make_session()

        await update_last_interaction(session, uid)

        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_commit_when_commit_false(self) -> None:
        from db.repositories.users import update_last_interaction
        uid = _uid()
        session = _make_session()

        await update_last_interaction(session, uid, commit=False)

        session.commit.assert_not_awaited()


class TestIncrements:

    @pytest.mark.asyncio
    async def test_increment_n_generated_images(self) -> None:
        from db.repositories.users import increment_n_generated_images
        uid = _uid()
        session = _make_session()
        count = fake.random_int(min=1, max=10)

        await increment_n_generated_images(session, uid, count)

        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_increment_n_transcribed_seconds(self) -> None:
        from db.repositories.users import increment_n_transcribed_seconds
        uid = _uid()
        session = _make_session()
        secs = fake.pyfloat(min_value=0.1, max_value=120.0, right_digits=2)

        await increment_n_transcribed_seconds(session, uid, secs)

        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()


class TestSetUserAdminAndWhitelisted:

    @pytest.mark.asyncio
    async def test_set_user_admin(self) -> None:
        from db.repositories.users import set_user_admin
        session = _make_session()
        await set_user_admin(session, _uid(), True)
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_set_user_whitelisted(self) -> None:
        from db.repositories.users import set_user_whitelisted
        session = _make_session()
        await set_user_whitelisted(session, _uid(), False)
        session.execute.assert_awaited_once()


class TestSyncAuthFromYaml:

    @pytest.mark.asyncio
    async def test_sync_updates_existing_users(self) -> None:
        from db.repositories.users import sync_auth_from_yaml
        uid1 = _uid()
        user = _fake_user_obj(uid1)
        user.is_admin = False
        user.is_whitelisted = False

        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        await sync_auth_from_yaml(session, admin_ids=[uid1], allowed_ids=[uid1])

        session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_sync_skips_unknown_users(self) -> None:
        from db.repositories.users import sync_auth_from_yaml
        uid = _uid()
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        await sync_auth_from_yaml(session, admin_ids=[uid], allowed_ids=[])
        session.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_sync_empty_lists_commits(self) -> None:
        from db.repositories.users import sync_auth_from_yaml
        session = _make_session()
        await sync_auth_from_yaml(session, admin_ids=[], allowed_ids=[])
        session.commit.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════
# db/repositories/dialogs.py (ключевые функции)
# ═══════════════════════════════════════════════════════════════════


class TestEnsureActiveDialog:

    @pytest.mark.asyncio
    async def test_returns_existing_dialog_id(self) -> None:
        from db.repositories.dialogs import ensure_active_dialog
        uid = _uid()
        did = _did()
        user = _fake_user_obj(uid)
        user.state.current_chat_mode = "assistant"
        user.state.current_dialog_ids ={"assistant": did}
        user.state.current_dialog_id =did

        session = _make_session()
        dialog_result = MagicMock()
        dialog_result.scalar_one_or_none.return_value = did

        def _execute_side_effect(query):
            return _scalar_result(user) if "User" in str(type(query)) or "users" in str(query).lower() else dialog_result

        session.execute.side_effect = [
            _scalar_result(user),  # get_user
            _scalar_result(did),   # dialog exists check
        ]

        result = await ensure_active_dialog(session, uid)
        assert result == did

    @pytest.mark.asyncio
    async def test_creates_new_dialog_when_none_exists(self) -> None:
        from db.repositories.dialogs import ensure_active_dialog
        uid = _uid()
        user = _fake_user_obj(uid)
        user.state.current_chat_mode = "assistant"
        user.state.current_dialog_ids ={}
        user.state.current_dialog_id =None

        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        result = await ensure_active_dialog(session, uid)
        assert result is not None
        session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_raises_when_user_not_found(self) -> None:
        from db.repositories.dialogs import ensure_active_dialog
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        with pytest.raises(ValueError, match="not found"):
            await ensure_active_dialog(session, _uid())


class TestStartNewDialog:

    @pytest.mark.asyncio
    async def test_creates_dialog_and_returns_id(self) -> None:
        from db.repositories.dialogs import start_new_dialog
        uid = _uid()
        user = _fake_user_obj(uid)
        user.state.current_chat_mode = "assistant"
        user.state.current_dialog_ids ={}
        user.state.current_dialog_id =None

        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        result = await start_new_dialog(session, uid)
        assert result is not None
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_raises_when_user_not_found(self) -> None:
        from db.repositories.dialogs import start_new_dialog
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        with pytest.raises(ValueError, match="not found"):
            await start_new_dialog(session, _uid())

    @pytest.mark.asyncio
    async def test_no_commit_when_commit_false(self) -> None:
        from db.repositories.dialogs import start_new_dialog
        uid = _uid()
        user = _fake_user_obj(uid)
        user.state.current_dialog_ids ={}
        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        await start_new_dialog(session, uid, commit=False)
        session.commit.assert_not_awaited()


class TestGetDialogMessages:

    @pytest.mark.asyncio
    async def test_returns_dialog_messages(self) -> None:
        from db.repositories.dialogs import get_dialog_messages
        uid = _uid()
        did = _did()
        msgs = [{"user": fake.sentence(), "bot": fake.sentence()}]
        dialog = _fake_dialog_obj(uid, did)
        dialog.messages = msgs

        session = _make_session()
        session.execute.return_value = _scalar_result(dialog)

        result = await get_dialog_messages(session, uid, did)
        assert result == msgs

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_dialog_not_found(self) -> None:
        from db.repositories.dialogs import get_dialog_messages
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        result = await get_dialog_messages(session, _uid(), _did())
        assert result == []

    @pytest.mark.asyncio
    async def test_resolves_dialog_id_from_user_when_none(self) -> None:
        from db.repositories.dialogs import get_dialog_messages
        uid = _uid()
        did = _did()
        user = _fake_user_obj(uid)
        user.state.current_dialog_id =did
        dialog = _fake_dialog_obj(uid, did)
        dialog.messages = []

        session = _make_session()
        session.execute.side_effect = [
            _scalar_result(user),   # get_user
            _scalar_result(dialog), # dialog query
        ]

        result = await get_dialog_messages(session, uid, dialog_id=None)
        assert result == []


class TestSetDialogMessages:

    @pytest.mark.asyncio
    async def test_updates_messages_with_dialog_id(self) -> None:
        from db.repositories.dialogs import set_dialog_messages
        session = _make_session()
        msgs = [{"user": fake.sentence(), "bot": fake.sentence()}]

        await set_dialog_messages(session, _uid(), msgs, _did())

        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_resolves_from_user_when_dialog_id_none(self) -> None:
        from db.repositories.dialogs import set_dialog_messages
        uid = _uid()
        user = _fake_user_obj(uid)
        user.state.current_dialog_id =_did()
        session = _make_session()
        session.execute.side_effect = [
            _scalar_result(user),   # get_user
            MagicMock(),            # update
        ]

        await set_dialog_messages(session, uid, [], dialog_id=None)
        assert session.execute.await_count == 2


class TestUpdateNUsedTokens:

    @pytest.mark.asyncio
    async def test_accumulates_tokens_for_model(self) -> None:
        from db.repositories.dialogs import update_n_used_tokens
        uid = _uid()
        model = "gpt-4o"
        stats = _fake_stats()

        session = _make_session()
        session.execute.side_effect = [
            _scalar_result(stats),  # SELECT FOR UPDATE (UserStatistics)
            MagicMock(),            # UPDATE
        ]
        n_in = fake.random_int(min=10, max=1000)
        n_out = fake.random_int(min=5, max=500)

        await update_n_used_tokens(session, uid, model, n_in, n_out)
        session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_no_op_when_user_not_found(self) -> None:
        from db.repositories.dialogs import update_n_used_tokens
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        await update_n_used_tokens(session, _uid(), "gpt-4o", 10, 5)
        session.commit.assert_not_awaited()


class TestAppendDialogMessage:

    @pytest.mark.asyncio
    async def test_appends_message_to_existing_dialog(self) -> None:
        from db.repositories.dialogs import append_messages
        from services.messages import user_message
        uid = _uid()
        did = _did()
        dialog = _fake_dialog_obj(uid, did)
        dialog.messages = [{"id": "msg_0", "role": "user", "content": "old"}]

        session = _make_session()
        session.execute.side_effect = [
            _scalar_result(dialog),  # SELECT FOR UPDATE
            MagicMock(),             # UPDATE
        ]

        await append_messages(session, uid, did, [user_message(fake.sentence())])
        session.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_skips_when_dialog_not_found(self) -> None:
        from db.repositories.dialogs import append_messages
        from services.messages import user_message
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        ok = await append_messages(session, _uid(), _did(), [user_message("x")])
        assert ok is False
        # не должно падать, execute вызван один раз (SELECT FOR UPDATE)
        session.execute.assert_awaited_once()
