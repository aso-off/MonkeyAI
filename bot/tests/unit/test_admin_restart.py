"""
Тесты для bot/src/bot/routers/admin/restart.py.

Покрываем:
- _do_restart()    — SSH успех (returncode 0), ошибка returncode, SSH exception
- cmd_restart()    — не admin, нет SSH hostname, лок занят,
                     нормальный флоу, ошибка сохранения в Redis
- cb_admin_restart() — не admin, нет hostname, лок занят,
                       нормальный флоу, ошибка edit_text (логируется)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message
from faker import Faker

fake = Faker()
Faker.seed(42)

def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)

def _fake_settings(admin_ids=None, has_hostname=True):
    s = MagicMock()
    s.admin_ids = admin_ids or [999_000_000]
    s.ssh_connection = {
        "hostname": "server.example.com" if has_hostname else "",
        "username": "root",
        "password": "secret",
        "timeout": 30,
        "project_path": "/root/project",
    }
    return s

def _fake_redis() -> AsyncMock:
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock()
    r.delete = AsyncMock()
    return r

def _fake_message(uid: int | None = None) -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = uid or _uid()
    msg.chat = MagicMock()
    msg.chat.id = msg.from_user.id
    reply = MagicMock()
    reply.message_id = fake.random_int(min=1, max=99999)
    msg.answer = AsyncMock(return_value=reply)
    return msg

def _fake_callback(uid: int | None = None) -> MagicMock:
    cb = MagicMock()
    cb.data = "admin_restart"
    cb.from_user = MagicMock()
    cb.from_user.id = uid or _uid()
    cb.answer = AsyncMock()
    cb.message = MagicMock(spec=Message)
    cb.message.message_id = fake.random_int(min=1, max=99999)
    cb.message.edit_text = AsyncMock()
    cb.message.reply_markup = MagicMock()
    return cb

# _do_restart

class TestDoRestart:

    @pytest.mark.asyncio
    async def test_success_does_not_delete_lock(self) -> None:
        from src.bot.routers.admin.restart import _do_restart
        redis = _fake_redis()
        conn = AsyncMock()
        conn.run = AsyncMock(return_value=MagicMock(returncode=0, stderr=""))
        with patch("src.bot.routers.admin.restart.settings",
                   _fake_settings()), \
             patch("src.bot.routers.admin.restart.asyncssh.connect") as mock_ssh:
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=conn)
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            await _do_restart(redis)
        redis.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_nonzero_returncode_deletes_lock(self) -> None:
        from src.bot.routers.admin.restart import _do_restart
        redis = _fake_redis()
        conn = AsyncMock()
        conn.run = AsyncMock(return_value=MagicMock(returncode=1, stderr="error"))
        with patch("src.bot.routers.admin.restart.settings",
                   _fake_settings()), \
             patch("src.bot.routers.admin.restart.asyncssh.connect") as mock_ssh:
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=conn)
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            await _do_restart(redis)
        redis.delete.assert_awaited()

    @pytest.mark.asyncio
    async def test_ssh_exception_deletes_lock(self) -> None:
        from src.bot.routers.admin.restart import _do_restart
        redis = _fake_redis()
        with patch("src.bot.routers.admin.restart.settings",
                   _fake_settings()), \
             patch("src.bot.routers.admin.restart.asyncssh.connect",
                   side_effect=OSError("connection refused")):
            await _do_restart(redis)
        redis.delete.assert_awaited_with("restart_in_progress")

# cmd_restart

class TestCmdRestart:

    @pytest.mark.asyncio
    async def test_not_admin_returns_silently(self) -> None:
        from src.bot.routers.admin.restart import cmd_restart
        uid = _uid()
        msg = _fake_message(uid=uid)
        with patch("src.bot.routers.admin.restart.settings",
                   _fake_settings(admin_ids=[uid + 1])):
            await cmd_restart(msg, language="ru")
        msg.answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_ssh_hostname_sends_error(self) -> None:
        from src.bot.routers.admin.restart import cmd_restart
        uid = 999_000_000
        msg = _fake_message(uid=uid)
        redis = _fake_redis()
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.bot.routers.admin.restart.settings",
                   _fake_settings(admin_ids=[uid], has_hostname=False)), \
             patch("src.core.bot.dp", mock_dp), \
             patch("src.bot.routers.admin.restart.t", return_value="not configured"):
            await cmd_restart(msg, language="ru")
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lock_exists_sends_already_in_progress(self) -> None:
        from src.bot.routers.admin.restart import cmd_restart
        uid = 999_000_000
        msg = _fake_message(uid=uid)
        redis = _fake_redis()
        redis.get = AsyncMock(return_value=b"1")
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.bot.routers.admin.restart.settings",
                   _fake_settings(admin_ids=[uid])), \
             patch("src.core.bot.dp", mock_dp), \
             patch("src.bot.routers.admin.restart.t", return_value="in progress"):
            await cmd_restart(msg, language="ru")
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_normal_flow_calls_do_restart(self) -> None:
        from src.bot.routers.admin.restart import cmd_restart
        uid = 999_000_000
        msg = _fake_message(uid=uid)
        redis = _fake_redis()
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.bot.routers.admin.restart.settings",
                   _fake_settings(admin_ids=[uid])), \
             patch("src.core.bot.dp", mock_dp), \
             patch("src.bot.routers.admin.restart.t", return_value="restarting"), \
             patch("src.bot.routers.admin.restart._do_restart",
                   AsyncMock()) as mock_restart:
            await cmd_restart(msg, language="ru")
        mock_restart.assert_awaited_once_with(redis)

    @pytest.mark.asyncio
    async def test_redis_save_error_returns_early(self) -> None:
        from src.bot.routers.admin.restart import cmd_restart
        uid = 999_000_000
        msg = _fake_message(uid=uid)
        redis = _fake_redis()
        # первый setex (restart_in_progress) проходит, второй (restart:chat_id) — нет
        call_count = [0]
        async def _setex(*a, **kw):
            call_count[0] += 1
            if call_count[0] > 1:
                raise RuntimeError("redis down")
        redis.setex = _setex
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.bot.routers.admin.restart.settings",
                   _fake_settings(admin_ids=[uid])), \
             patch("src.core.bot.dp", mock_dp), \
             patch("src.bot.routers.admin.restart.t", return_value=""), \
             patch("src.bot.routers.admin.restart._do_restart",
                   AsyncMock()) as mock_restart:
            await cmd_restart(msg, language="ru")
        mock_restart.assert_not_awaited()

# cb_admin_restart

class TestCbAdminRestart:

    @pytest.mark.asyncio
    async def test_not_admin_answers_denied(self) -> None:
        from src.bot.routers.admin.restart import cb_admin_restart
        uid = _uid()
        cb = _fake_callback(uid=uid)
        with patch("src.bot.routers.admin.restart.settings",
                   _fake_settings(admin_ids=[uid + 1])), \
             patch("src.bot.routers.admin.restart.t", return_value="denied"):
            await cb_admin_restart(cb, language="ru")
        cb.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_hostname_answers_error(self) -> None:
        from src.bot.routers.admin.restart import cb_admin_restart
        uid = 999_000_000
        cb = _fake_callback(uid=uid)
        redis = _fake_redis()
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.bot.routers.admin.restart.settings",
                   _fake_settings(admin_ids=[uid], has_hostname=False)), \
             patch("src.core.bot.dp", mock_dp), \
             patch("src.bot.routers.admin.restart.t", return_value="not configured"):
            await cb_admin_restart(cb, language="ru")
        cb.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lock_exists_answers_in_progress(self) -> None:
        from src.bot.routers.admin.restart import cb_admin_restart
        uid = 999_000_000
        cb = _fake_callback(uid=uid)
        redis = _fake_redis()
        redis.get = AsyncMock(return_value=b"1")
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.bot.routers.admin.restart.settings",
                   _fake_settings(admin_ids=[uid])), \
             patch("src.core.bot.dp", mock_dp), \
             patch("src.bot.routers.admin.restart.t", return_value="in progress"):
            await cb_admin_restart(cb, language="ru")
        cb.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_normal_flow_edits_and_calls_restart(self) -> None:
        from src.bot.routers.admin.restart import cb_admin_restart
        uid = 999_000_000
        cb = _fake_callback(uid=uid)
        redis = _fake_redis()
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.bot.routers.admin.restart.settings",
                   _fake_settings(admin_ids=[uid])), \
             patch("src.core.bot.dp", mock_dp), \
             patch("src.bot.routers.admin.restart.t", return_value="restarting"), \
             patch("src.bot.routers.admin.restart._do_restart",
                   AsyncMock()) as mock_restart:
            await cb_admin_restart(cb, language="ru")
        mock_restart.assert_awaited_once_with(redis)
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_edit_exception_is_logged_not_raised(self) -> None:
        from src.bot.routers.admin.restart import cb_admin_restart
        uid = 999_000_000
        cb = _fake_callback(uid=uid)
        cb.message.edit_text = AsyncMock(side_effect=Exception("edit error"))
        redis = _fake_redis()
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.bot.routers.admin.restart.settings",
                   _fake_settings(admin_ids=[uid])), \
             patch("src.core.bot.dp", mock_dp), \
             patch("src.bot.routers.admin.restart.t", return_value=""), \
             patch("src.bot.routers.admin.restart._do_restart", AsyncMock()):
            await cb_admin_restart(cb, language="ru")
        # Не упало

    @pytest.mark.asyncio
    async def test_redis_save_error_returns_early(self) -> None:
        from src.bot.routers.admin.restart import cb_admin_restart
        uid = 999_000_000
        cb = _fake_callback(uid=uid)
        redis = _fake_redis()
        call_count = [0]
        async def _setex(*a, **kw):
            call_count[0] += 1
            if call_count[0] > 1:
                raise RuntimeError("redis down")
        redis.setex = _setex
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.bot.routers.admin.restart.settings",
                   _fake_settings(admin_ids=[uid])), \
             patch("src.core.bot.dp", mock_dp), \
             patch("src.bot.routers.admin.restart.t", return_value=""), \
             patch("src.bot.routers.admin.restart._do_restart",
                   AsyncMock()) as mock_restart:
            await cb_admin_restart(cb, language="ru")
        mock_restart.assert_not_awaited()
