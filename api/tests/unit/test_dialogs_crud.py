"""Репо-тесты CRUD диалогов (Фаза 2) и галереи (Фаза 3)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    s.commit = AsyncMock()
    s.execute = AsyncMock()
    return s


def _scalars(values: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = values
    return r


def _rows(values: list) -> MagicMock:
    r = MagicMock()
    r.all.return_value = values
    return r


def _fake_row(title) -> MagicMock:
    d = MagicMock()
    d.id = str(uuid.uuid4())
    d.title = title
    d.last_activity = datetime.now(timezone.utc)
    d.start_time = datetime.now(timezone.utc)
    d.pinned_at = None
    return d


def _rowcount(n: int) -> MagicMock:
    r = MagicMock()
    r.rowcount = n
    return r


def _fake_dialog() -> MagicMock:
    d = MagicMock()
    d.id = str(uuid.uuid4())
    d.title = "t"
    d.last_activity = datetime.now(timezone.utc)
    d.start_time = datetime.now(timezone.utc)
    return d


@pytest.mark.asyncio
async def test_list_dialogs_returns_rows() -> None:
    from db.repositories.dialogs import list_dialogs
    session = _make_session()
    session.execute.return_value = _scalars([_fake_dialog(), _fake_dialog()])
    rows = await list_dialogs(session, 123, None, 20)
    assert len(rows) == 2
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_dialogs_with_cursor() -> None:
    from db.repositories.dialogs import list_dialogs
    session = _make_session()
    session.execute.return_value = _scalars([_fake_dialog()])
    rows = await list_dialogs(session, 123, datetime.now(timezone.utc), 10)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_search_dialogs_returns_rows() -> None:
    from db.repositories.dialogs import search_dialogs
    session = _make_session()
    session.execute.return_value = _rows([_fake_row("Docker"), _fake_row("прочее")])
    rows = await search_dialogs(session, 123, "doc", 50)  # регистр игнорируется
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_search_dialogs_case_insensitive_cyrillic() -> None:
    from db.repositories.dialogs import search_dialogs
    session = _make_session()
    session.execute.return_value = _rows([_fake_row("Мультяшка"), _fake_row("Docker")])
    rows = await search_dialogs(session, 123, "мульт", 50)
    assert len(rows) == 1
    assert rows[0].title == "Мультяшка"


@pytest.mark.asyncio
async def test_search_dialogs_include_untitled_branch() -> None:
    from db.repositories.dialogs import search_dialogs
    session = _make_session()
    session.execute.return_value = _rows([_fake_row(None), _fake_row("прочее")])
    rows = await search_dialogs(session, 123, "Новый чат", 50, include_untitled=True)
    assert len(rows) == 1
    assert rows[0].title is None


@pytest.mark.asyncio
async def test_rename_dialog_true_when_rowcount() -> None:
    from db.repositories.dialogs import rename_dialog
    session = _make_session()
    session.execute.return_value = _rowcount(1)
    assert await rename_dialog(session, 1, "did", "Новое") is True
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_rename_dialog_false_when_not_found() -> None:
    from db.repositories.dialogs import rename_dialog
    session = _make_session()
    session.execute.return_value = _rowcount(0)
    assert await rename_dialog(session, 1, "did", "Новое") is False


@pytest.mark.asyncio
async def test_delete_dialog_true_and_false() -> None:
    from db.repositories.dialogs import delete_dialog
    session = _make_session()
    session.execute.return_value = _rowcount(1)
    assert await delete_dialog(session, 1, "did") is True
    session.execute.return_value = _rowcount(0)
    assert await delete_dialog(session, 1, "did") is False


@pytest.mark.asyncio
async def test_add_generated_image_commits() -> None:
    from db.repositories.images import add_generated_image
    session = _make_session()
    await add_generated_image(session, 1, "did", "https://cdn/x", "промпт")
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_images_returns_rows() -> None:
    from db.repositories.images import list_images
    session = _make_session()
    session.execute.return_value = _scalars([MagicMock(), MagicMock()])
    rows = await list_images(session, 1, None, 30)
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_list_images_with_cursor() -> None:
    from db.repositories.images import list_images
    session = _make_session()
    session.execute.return_value = _scalars([MagicMock()])
    rows = await list_images(session, 1, datetime.now(timezone.utc), 30)
    assert len(rows) == 1