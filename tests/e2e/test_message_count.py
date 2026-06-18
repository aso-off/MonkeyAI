import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_counts_only_user_messages(client, seed):
    """Фикс ×2: N обменов (user+assistant) → счётчик = N, а не 2N. Реальный PG-SQL (json_array_elements)."""
    uid, did = await seed()

    from db.db import Session
    from db.repositories import dialogs as dialog_repo
    from services.messages import assistant_message, user_message

    async with Session() as s:
        for i in range(3):
            um = user_message(f"q{i}")
            am = assistant_message(f"a{i}", parent_id=um["id"], model="gpt-5.4-nano")
            await dialog_repo.append_messages(s, uid, did, [um, am])

        count = await dialog_repo.get_user_message_count(s, uid)

    assert count == 3


@pytest.mark.asyncio
async def test_zero_for_empty_user(client, seed):
    uid, _ = await seed()

    from db.db import Session
    from db.repositories import dialogs as dialog_repo

    async with Session() as s:
        assert await dialog_repo.get_user_message_count(s, uid) == 0
