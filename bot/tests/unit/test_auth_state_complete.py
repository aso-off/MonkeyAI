"""
Расширенные тесты для bot/src/core/auth_state.py.

Покрываем:
- reload_sync()       — читает YAML, заполняет _admin_ids/_allowed_ids
- reload_sync()       — обработка исключений (файл отсутствует)
- reload()            — вызывает asyncio.to_thread(reload_sync)
- is_allowed_cached() — Redis sismember, exists, ошибка Redis

Faker: user IDs, YAML-контент.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)


def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)


# ── reload_sync ───────────────────────────────────────────────────────────────


class TestReloadSync:

    def test_loads_admin_and_allowed_ids_from_yaml(self) -> None:
        from src.core import auth_state
        admin_id = _uid()
        allowed_id = _uid()
        yaml_content = (
            f"admin_user_ids:\n- {admin_id}\n"
            f"allowed_user_ids:\n- {allowed_id}\n"
        )

        mock_path = MagicMock(spec=Path)
        mock_path.read_text.return_value = yaml_content

        with patch.object(auth_state, "_USER_IDS_PATH", mock_path):
            auth_state.reload_sync()

        assert admin_id in auth_state._admin_ids
        assert allowed_id in auth_state._allowed_ids

    def test_handles_missing_file_gracefully(self) -> None:
        from src.core import auth_state
        mock_path = MagicMock(spec=Path)
        mock_path.read_text.side_effect = FileNotFoundError("file not found")

        original_admins = auth_state._admin_ids.copy()
        original_allowed = auth_state._allowed_ids.copy()

        with patch.object(auth_state, "_USER_IDS_PATH", mock_path):
            auth_state.reload_sync()  # не должен падать

    def test_parses_multiple_admin_ids(self) -> None:
        from src.core import auth_state
        ids = [_uid() for _ in range(3)]
        yaml_content = "admin_user_ids:\n" + "\n".join(f"- {i}" for i in ids) + "\nallowed_user_ids: []\n"

        mock_path = MagicMock(spec=Path)
        mock_path.read_text.return_value = yaml_content

        with patch.object(auth_state, "_USER_IDS_PATH", mock_path):
            auth_state.reload_sync()

        for uid in ids:
            assert uid in auth_state._admin_ids

    def test_empty_yaml_results_in_empty_sets(self) -> None:
        from src.core import auth_state
        mock_path = MagicMock(spec=Path)
        mock_path.read_text.return_value = "{}"

        with patch.object(auth_state, "_USER_IDS_PATH", mock_path):
            auth_state.reload_sync()

        assert isinstance(auth_state._admin_ids, set)
        assert isinstance(auth_state._allowed_ids, set)

    def test_faker_batch_ids(self) -> None:
        from src.core import auth_state
        for _ in range(3):
            admin_id = _uid()
            allowed_id = _uid()
            yaml_content = (
                f"admin_user_ids:\n- {admin_id}\n"
                f"allowed_user_ids:\n- {allowed_id}\n"
            )
            mock_path = MagicMock(spec=Path)
            mock_path.read_text.return_value = yaml_content
            with patch.object(auth_state, "_USER_IDS_PATH", mock_path):
                auth_state.reload_sync()
            assert admin_id in auth_state._admin_ids


# ── reload ────────────────────────────────────────────────────────────────────


class TestReload:

    @pytest.mark.asyncio
    async def test_calls_asyncio_to_thread(self) -> None:
        from src.core import auth_state
        with patch("asyncio.to_thread", new=AsyncMock()) as mock_thread:
            await auth_state.reload()
        mock_thread.assert_awaited_once_with(auth_state.reload_sync)


# ── is_admin / is_allowed ─────────────────────────────────────────────────────


class TestIsAdminIsAllowed:

    def test_is_admin_true_when_in_admin_ids(self) -> None:
        from src.core import auth_state
        uid = _uid()
        original = auth_state._admin_ids.copy()
        auth_state._admin_ids.add(uid)
        try:
            assert auth_state.is_admin(uid) is True
        finally:
            auth_state._admin_ids = original

    def test_is_admin_false_when_not_in_admin_ids(self) -> None:
        from src.core import auth_state
        uid = _uid()
        original = auth_state._admin_ids.copy()
        auth_state._admin_ids.discard(uid)
        try:
            assert auth_state.is_admin(uid) is False
        finally:
            auth_state._admin_ids = original

    def test_is_allowed_true_when_in_allowed_ids(self) -> None:
        from src.core import auth_state
        uid = _uid()
        orig_allowed = auth_state._allowed_ids.copy()
        orig_admin = auth_state._admin_ids.copy()
        auth_state._allowed_ids.add(uid)
        auth_state._admin_ids.discard(uid)
        try:
            assert auth_state.is_allowed(uid) is True
        finally:
            auth_state._allowed_ids = orig_allowed
            auth_state._admin_ids = orig_admin

    def test_is_allowed_true_when_in_admin_ids(self) -> None:
        from src.core import auth_state
        uid = _uid()
        orig_admin = auth_state._admin_ids.copy()
        auth_state._admin_ids.add(uid)
        try:
            assert auth_state.is_allowed(uid) is True
        finally:
            auth_state._admin_ids = orig_admin

    def test_is_allowed_false_when_neither(self) -> None:
        from src.core import auth_state
        uid = _uid()
        orig_allowed = auth_state._allowed_ids.copy()
        orig_admin = auth_state._admin_ids.copy()
        auth_state._allowed_ids.discard(uid)
        auth_state._admin_ids.discard(uid)
        try:
            assert auth_state.is_allowed(uid) is False
        finally:
            auth_state._allowed_ids = orig_allowed
            auth_state._admin_ids = orig_admin


# ── is_allowed_cached ─────────────────────────────────────────────────────────


class TestIsAllowedCached:

    @pytest.mark.asyncio
    async def test_returns_true_when_sismember(self) -> None:
        import sys
        import types
        from src.core import auth_state
        uid = _uid()

        mock_redis = AsyncMock()
        mock_redis.sismember = AsyncMock(return_value=True)
        mock_dp = MagicMock()
        mock_dp.storage.redis = mock_redis

        # Стабим src.core.bot в sys.modules чтобы избежать реального импорта
        fake_bot_mod = types.SimpleNamespace(dp=mock_dp, bot=MagicMock())
        with patch.dict(sys.modules, {"src.core.bot": fake_bot_mod}):
            result = await auth_state.is_allowed_cached(uid)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_in_set_but_set_exists(self) -> None:
        import sys
        import types
        from src.core import auth_state
        uid = _uid()

        mock_redis = AsyncMock()
        mock_redis.sismember = AsyncMock(return_value=False)
        mock_redis.exists = AsyncMock(return_value=True)
        mock_dp = MagicMock()
        mock_dp.storage.redis = mock_redis

        fake_bot_mod = types.SimpleNamespace(dp=mock_dp, bot=MagicMock())
        with patch.dict(sys.modules, {"src.core.bot": fake_bot_mod}):
            result = await auth_state.is_allowed_cached(uid)

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_none_when_redis_raises(self) -> None:
        import sys
        import types
        from src.core import auth_state
        uid = _uid()

        mock_redis = AsyncMock()
        mock_redis.sismember = AsyncMock(side_effect=Exception("Redis down"))
        mock_dp = MagicMock()
        mock_dp.storage.redis = mock_redis

        fake_bot_mod = types.SimpleNamespace(dp=mock_dp, bot=MagicMock())
        with patch.dict(sys.modules, {"src.core.bot": fake_bot_mod}):
            result = await auth_state.is_allowed_cached(uid)

        assert result is None
