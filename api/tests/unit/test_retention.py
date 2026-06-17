"""Тесты сервиса retention (пакетная очистка диалогов и реакций)."""

import types
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_session() -> AsyncMock:
    s = AsyncMock()
    s.commit = AsyncMock()
    s.execute = AsyncMock()
    return s

def _scalars(values: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = values
    return r

@pytest.mark.asyncio
async def test_purge_single_batch_deletes_and_commits() -> None:
    from db.models.user import Dialog
    from services.retention import _purge

    session = _make_session()
    session.execute.side_effect = [_scalars(["a", "b"]), MagicMock()]
    n = await _purge(
        session, Dialog, Dialog.id, Dialog.last_activity,
        datetime.now(UTC), batch_size=500,
    )
    assert n == 2
    session.commit.assert_awaited_once()

@pytest.mark.asyncio
async def test_purge_loops_until_batch_not_full() -> None:
    from db.models.user import Reaction
    from services.retention import _purge

    session = _make_session()
    session.execute.side_effect = [
        _scalars([1, 2]), MagicMock(),  # полный батч → ещё итерация
        _scalars([3]), MagicMock(),     # неполный → стоп
    ]
    n = await _purge(
        session, Reaction, Reaction.id, Reaction.created_at,
        datetime.now(UTC), batch_size=2,
    )
    assert n == 3
    assert session.commit.await_count == 2

@pytest.mark.asyncio
async def test_purge_nothing_to_delete() -> None:
    from db.models.user import Dialog
    from services.retention import _purge

    session = _make_session()
    session.execute.side_effect = [_scalars([])]
    n = await _purge(
        session, Dialog, Dialog.id, Dialog.last_activity,
        datetime.now(UTC), batch_size=500,
    )
    assert n == 0
    session.commit.assert_not_awaited()

@pytest.mark.asyncio
async def test_cleanup_dialogs_uses_inactive_cutoff(monkeypatch) -> None:
    from db.models.user import Dialog
    from services import retention

    captured: dict = {}

    async def fake_purge(session, model, pk_col, time_col, cutoff, batch_size):
        captured.update(model=model, cutoff=cutoff, time_col=time_col)
        return 0

    monkeypatch.setattr(retention, "settings", types.SimpleNamespace(
        retention_dialogs_inactive_days=90, retention_reactions_days=90, retention_batch_size=500,
    ))
    monkeypatch.setattr(retention, "_purge", fake_purge)
    await retention.cleanup_dialogs(_make_session())

    assert captured["model"] is Dialog
    expected = datetime.now(UTC) - timedelta(days=90)
    assert abs((captured["cutoff"] - expected).total_seconds()) < 5

class _FakeSessionCM:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *a):
        return False

@pytest.mark.asyncio
async def test_run_once_calls_cleanups(monkeypatch) -> None:
    from services import retention
    monkeypatch.setattr(retention, "Session", lambda: _FakeSessionCM())
    monkeypatch.setattr(retention, "cleanup_dialogs", AsyncMock(return_value=3))
    monkeypatch.setattr(retention, "cleanup_reactions", AsyncMock(return_value=2))
    n_dialogs, n_reactions = await retention.run_once()
    assert (n_dialogs, n_reactions) == (3, 2)

@pytest.mark.asyncio
async def test_cleanup_reactions_uses_created_cutoff(monkeypatch) -> None:
    from db.models.user import Reaction
    from services import retention

    captured: dict = {}

    async def fake_purge(session, model, pk_col, time_col, cutoff, batch_size):
        captured.update(model=model, cutoff=cutoff)
        return 0

    monkeypatch.setattr(retention, "settings", types.SimpleNamespace(
        retention_dialogs_inactive_days=90, retention_reactions_days=90, retention_batch_size=500,
    ))
    monkeypatch.setattr(retention, "_purge", fake_purge)
    await retention.cleanup_reactions(_make_session())

    assert captured["model"] is Reaction
    expected = datetime.now(UTC) - timedelta(days=90)
    assert abs((captured["cutoff"] - expected).total_seconds()) < 5
