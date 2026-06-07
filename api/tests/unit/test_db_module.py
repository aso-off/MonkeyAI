"""
Тесты для api/src/db/db.py.

Покрываем:
- get_session()  — async generator (lines 17-18 не покрыты т.к. routes-тесты
  используют dependency_overrides, который обходит реальную функцию)
- init_db()      — lines 22-34
- Base           — DeclarativeBase (lines 7-8)

Нюанс: AsyncEngine.begin — read-only property; патчим через mock.patch("db.db.engine").
"""

from unittest import mock

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_engine_mock():
    mock_conn = mock.AsyncMock()
    mock_begin_ctx = mock.MagicMock()
    mock_begin_ctx.__aenter__ = mock.AsyncMock(return_value=mock_conn)
    mock_begin_ctx.__aexit__ = mock.AsyncMock(return_value=False)

    mock_engine = mock.MagicMock()
    mock_engine.begin = mock.MagicMock(return_value=mock_begin_ctx)
    return mock_engine, mock_conn


def _make_session_mock():
    mock_session = mock.AsyncMock()
    mock_ctx = mock.MagicMock()
    mock_ctx.__aenter__ = mock.AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = mock.AsyncMock(return_value=False)
    mock_factory = mock.MagicMock(return_value=mock_ctx)
    return mock_factory, mock_session, mock_ctx


# ── get_session ───────────────────────────────────────────────────────────────


class TestGetSession:

    @pytest.mark.asyncio
    async def test_get_session_yields_session(self) -> None:
        from db.db import get_session
        mock_factory, mock_session, _ = _make_session_mock()

        with mock.patch("db.db.Session", mock_factory):
            gen = get_session()
            session = await gen.__anext__()

        assert session is mock_session

    @pytest.mark.asyncio
    async def test_get_session_closes_on_exit(self) -> None:
        from db.db import get_session
        mock_factory, _, mock_ctx = _make_session_mock()

        with mock.patch("db.db.Session", mock_factory):
            gen = get_session()
            await gen.__anext__()
            try:
                await gen.asend(None)
            except StopAsyncIteration:
                pass

        mock_ctx.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session_is_async_generator(self) -> None:
        import inspect
        from db.db import get_session
        assert inspect.isasyncgenfunction(get_session)

    @pytest.mark.asyncio
    async def test_get_session_calls_session_factory(self) -> None:
        from db.db import get_session
        mock_factory, _, _ = _make_session_mock()

        with mock.patch("db.db.Session", mock_factory):
            gen = get_session()
            await gen.__anext__()
            try:
                await gen.asend(None)
            except StopAsyncIteration:
                pass

        mock_factory.assert_called_once()


# ── init_db ───────────────────────────────────────────────────────────────────


class TestInitDb:

    @pytest.mark.asyncio
    async def test_init_db_calls_create_all(self) -> None:
        from db.db import init_db
        mock_engine, mock_conn = _make_engine_mock()

        with mock.patch("db.db.engine", mock_engine):
            await init_db()

        mock_conn.run_sync.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_init_db_calls_alter_table_6_times(self) -> None:
        from db.db import init_db
        mock_engine, mock_conn = _make_engine_mock()

        with mock.patch("db.db.engine", mock_engine):
            await init_db()

        assert mock_conn.exec_driver_sql.await_count == 6

    @pytest.mark.asyncio
    async def test_init_db_adds_is_admin_column(self) -> None:
        from db.db import init_db
        mock_engine, mock_conn = _make_engine_mock()

        with mock.patch("db.db.engine", mock_engine):
            await init_db()

        sqls = [str(c.args[0]) for c in mock_conn.exec_driver_sql.call_args_list]
        assert any("is_admin" in s for s in sqls)

    @pytest.mark.asyncio
    async def test_init_db_adds_is_whitelisted_column(self) -> None:
        from db.db import init_db
        mock_engine, mock_conn = _make_engine_mock()

        with mock.patch("db.db.engine", mock_engine):
            await init_db()

        sqls = [str(c.args[0]) for c in mock_conn.exec_driver_sql.call_args_list]
        assert any("is_whitelisted" in s for s in sqls)

    @pytest.mark.asyncio
    async def test_init_db_adds_theme_column(self) -> None:
        from db.db import init_db
        mock_engine, mock_conn = _make_engine_mock()

        with mock.patch("db.db.engine", mock_engine):
            await init_db()

        sqls = [str(c.args[0]) for c in mock_conn.exec_driver_sql.call_args_list]
        assert any("theme" in s for s in sqls)

    @pytest.mark.asyncio
    async def test_init_db_adds_mini_app_chat_mode_column(self) -> None:
        from db.db import init_db
        mock_engine, mock_conn = _make_engine_mock()

        with mock.patch("db.db.engine", mock_engine):
            await init_db()

        sqls = [str(c.args[0]) for c in mock_conn.exec_driver_sql.call_args_list]
        assert any("mini_app_chat_mode" in s for s in sqls)

    @pytest.mark.asyncio
    async def test_init_db_uses_add_column_if_not_exists(self) -> None:
        from db.db import init_db
        mock_engine, mock_conn = _make_engine_mock()

        with mock.patch("db.db.engine", mock_engine):
            await init_db()

        sqls = [str(c.args[0]) for c in mock_conn.exec_driver_sql.call_args_list]
        assert all("ADD COLUMN IF NOT EXISTS" in s for s in sqls)


# ── Base & module-level ───────────────────────────────────────────────────────


class TestBaseAndEngine:

    def test_base_is_declarative_base(self) -> None:
        from db.db import Base
        from sqlalchemy.orm import DeclarativeBase
        assert issubclass(Base, DeclarativeBase)

    def test_engine_is_not_none(self) -> None:
        from db.db import engine
        assert engine is not None

    def test_session_factory_is_not_none(self) -> None:
        from db.db import Session
        assert Session is not None

    def test_engine_url_contains_testdb(self) -> None:
        from db.db import engine
        url_str = str(engine.url)
        assert "testdb" in url_str

    def test_faker_random_does_not_affect_engine(self) -> None:
        from db.db import engine
        for _ in range(3):
            _ = fake.random_int(min=1, max=1000)
        assert engine is not None
