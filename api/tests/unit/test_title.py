"""Тесты заголовков чатов: обрезка, nano-суммаризация, set_initial_title, оркестратор."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_session() -> AsyncMock:
    s = AsyncMock()
    s.commit = AsyncMock()
    s.execute = AsyncMock()
    return s


def _scalar_result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


# ── truncate_title ────────────────────────────────────────────────────────────

def test_truncate_short_stays() -> None:
    from services.title import truncate_title
    assert truncate_title("Привет мир") == "Привет мир"


def test_truncate_normalizes_whitespace() -> None:
    from services.title import truncate_title
    assert truncate_title("  привет   мир  ") == "привет мир"


def test_truncate_word_boundary_with_ellipsis() -> None:
    from services.title import truncate_title
    out = truncate_title("Что такое Docker и зачем он нужен в разработке сегодня вечером")
    assert len(out) <= 40
    assert out.endswith("…")
    assert not out[:-1].endswith(" ")


def test_truncate_single_huge_word_hard_cut() -> None:
    from services.title import truncate_title
    out = truncate_title("a" * 100)
    assert len(out) == 40
    assert out.endswith("…")


# ── summarize_title ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_summarize_title_clamps_and_strips(monkeypatch) -> None:
    from services import title
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = '"Очень длинный заголовок который точно больше сорока символов ага"'
    resp.usage.prompt_tokens = 12
    resp.usage.completion_tokens = 7
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=resp)
    monkeypatch.setattr(title, "_title_client", lambda: client)

    out, n_in, n_out = await title.summarize_title("длинный текст пользователя")
    assert len(out) <= 40
    assert not out.startswith('"')
    assert (n_in, n_out) == (12, 7)


# ── set_initial_title / update_dialog_title ───────────────────────────────────

@pytest.mark.asyncio
async def test_set_initial_title_sets_when_none() -> None:
    from db.repositories.dialogs import set_initial_title
    dialog = MagicMock()
    dialog.title = None
    session = _make_session()
    session.execute.return_value = _scalar_result(dialog)

    out = await set_initial_title(session, "did", "Что такое Docker")
    assert out == "Что такое Docker"
    assert dialog.title == "Что такое Docker"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_initial_title_noop_when_already_titled() -> None:
    from db.repositories.dialogs import set_initial_title
    dialog = MagicMock()
    dialog.title = "Уже есть"
    session = _make_session()
    session.execute.return_value = _scalar_result(dialog)

    out = await set_initial_title(session, "did", "текст")
    assert out is None
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_initial_title_noop_when_dialog_missing() -> None:
    from db.repositories.dialogs import set_initial_title
    session = _make_session()
    session.execute.return_value = _scalar_result(None)

    out = await set_initial_title(session, "did", "текст")
    assert out is None


@pytest.mark.asyncio
async def test_update_dialog_title_commits() -> None:
    from db.repositories.dialogs import update_dialog_title
    session = _make_session()
    await update_dialog_title(session, "did", "Новый заголовок")
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


# ── handle_first_message_title (оркестратор) ──────────────────────────────────

@pytest.mark.asyncio
async def test_handle_schedules_refine_on_first_message(monkeypatch) -> None:
    from services import title
    monkeypatch.setattr("db.repositories.dialogs.set_initial_title", AsyncMock(return_value="Заголовок"))
    refine = AsyncMock()
    monkeypatch.setattr(title, "_refine_title", refine)

    await title.handle_first_message_title(MagicMock(), "did", "текст")
    await asyncio.sleep(0)
    refine.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_noop_when_already_titled(monkeypatch) -> None:
    from services import title
    monkeypatch.setattr("db.repositories.dialogs.set_initial_title", AsyncMock(return_value=None))
    refine = AsyncMock()
    monkeypatch.setattr(title, "_refine_title", refine)

    await title.handle_first_message_title(MagicMock(), "did", "текст")
    await asyncio.sleep(0)
    refine.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_initial_title_empty_text_returns_none() -> None:
    from db.repositories.dialogs import set_initial_title
    dialog = MagicMock()
    dialog.title = None
    session = _make_session()
    session.execute.return_value = _scalar_result(dialog)

    out = await set_initial_title(session, "did", "   ")
    assert out is None
    session.commit.assert_not_awaited()


class _FakeSessionCM:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *a):
        return False


@pytest.mark.asyncio
async def test_refine_title_updates_and_broadcasts(monkeypatch) -> None:
    from services import title
    monkeypatch.setattr(title, "summarize_title", AsyncMock(return_value=("Готовый заголовок", 5, 3)))
    upd = AsyncMock()
    monkeypatch.setattr("db.repositories.dialogs.update_dialog_title", upd)
    monkeypatch.setattr("db.db.Session", lambda: _FakeSessionCM())
    on_ref = AsyncMock()

    await title._refine_title("did", None, "текст", "ответ", on_ref)
    upd.assert_awaited_once()
    on_ref.assert_awaited_once_with("Готовый заголовок")


@pytest.mark.asyncio
async def test_refine_title_records_tokens(monkeypatch) -> None:
    from services import title
    monkeypatch.setattr(title, "summarize_title", AsyncMock(return_value=("Заголовок", 5, 3)))
    monkeypatch.setattr("db.repositories.dialogs.update_dialog_title", AsyncMock())
    tokens = AsyncMock()
    monkeypatch.setattr("db.repositories.dialogs.update_n_used_tokens", tokens)
    monkeypatch.setattr("db.db.Session", lambda: _FakeSessionCM())

    await title._refine_title("did", 42, "текст", "ответ", None)
    tokens.assert_awaited_once()
    assert tokens.await_args is not None
    assert tokens.await_args.args[1:] == (42, "gpt-5.4-nano", 5, 3)


@pytest.mark.asyncio
async def test_refine_title_skips_when_empty(monkeypatch) -> None:
    from services import title
    monkeypatch.setattr(title, "summarize_title", AsyncMock(return_value=("", 0, 0)))
    upd = AsyncMock()
    monkeypatch.setattr("db.repositories.dialogs.update_dialog_title", upd)

    await title._refine_title("did", None, "текст", None, None)
    upd.assert_not_awaited()


@pytest.mark.asyncio
async def test_refine_title_swallows_errors(monkeypatch) -> None:
    from services import title
    monkeypatch.setattr(title, "summarize_title", AsyncMock(side_effect=RuntimeError("boom")))
    await title._refine_title("did", None, "текст", None, None)  # не должно бросить
