"""
Тесты для api/src/routes/dialogs.py.

Покрываем все 5 эндпоинтов:
- POST /{user_id}/new
- POST /{user_id}/ensure
- GET  /{user_id}/messages
- POST /{user_id}/pop-last
- POST /{user_id}/exchange
- GET  /{user_id}/message-count

Faker используется для user_id, dialog_id, сообщений, счётчиков токенов.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

# Helpers

def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)

def _did() -> str:
    return str(uuid.uuid4())

def _fake_messages(n: int = 3) -> list:
    return [{"user": fake.sentence(), "bot": fake.sentence()} for _ in range(n)]

# POST /{user_id}/new

class TestNewDialog:

    @pytest.mark.api
    def test_new_dialog_returns_200_with_dialog_id(self, api_client, user_factory) -> None:
        user = user_factory()
        dialog_id = _did()

        with patch("routes.dialogs.user_repo.get_user", new=AsyncMock(return_value=user)), \
             patch("routes.dialogs.dialog_repo.start_new_dialog",
                   new=AsyncMock(return_value=dialog_id)):
            resp = api_client.post(f"/dialogs/{user.id}/new")

        assert resp.status_code == 200
        assert resp.json()["dialog_id"] == dialog_id

    @pytest.mark.api
    def test_new_dialog_user_not_found_returns_404(self, api_client) -> None:
        uid = _uid()
        with patch("routes.dialogs.user_repo.get_user", new=AsyncMock(return_value=None)):
            resp = api_client.post(f"/dialogs/{uid}/new")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.api
    def test_faker_batch_new_dialogs(self, api_client, user_factory) -> None:
        for _ in range(3):
            user = user_factory()
            did = _did()
            with patch("routes.dialogs.user_repo.get_user", new=AsyncMock(return_value=user)), \
                 patch("routes.dialogs.dialog_repo.start_new_dialog",
                       new=AsyncMock(return_value=did)):
                resp = api_client.post(f"/dialogs/{user.id}/new")
            assert resp.status_code == 200
            assert resp.json()["dialog_id"] == did

# POST /{user_id}/ensure

class TestEnsureDialog:

    @pytest.mark.api
    def test_ensure_returns_200_with_dialog_id_and_messages(
        self, api_client, user_factory
    ) -> None:
        user = user_factory()
        did = _did()
        msgs = _fake_messages()

        with patch("routes.dialogs.user_repo.get_user", new=AsyncMock(return_value=user)), \
             patch("routes.dialogs.dialog_repo.ensure_active_dialog",
                   new=AsyncMock(return_value=did)), \
             patch("routes.dialogs.dialog_repo.get_dialog_messages",
                   new=AsyncMock(return_value=msgs)):
            resp = api_client.post(f"/dialogs/{user.id}/ensure")

        assert resp.status_code == 200
        data = resp.json()
        assert data["dialog_id"] == did
        assert data["messages"] == msgs

    @pytest.mark.api
    def test_ensure_user_not_found_returns_404(self, api_client) -> None:
        uid = _uid()
        with patch("routes.dialogs.user_repo.get_user", new=AsyncMock(return_value=None)):
            resp = api_client.post(f"/dialogs/{uid}/ensure")
        assert resp.status_code == 404

    @pytest.mark.api
    def test_ensure_empty_messages_list(self, api_client, user_factory) -> None:
        user = user_factory()
        did = _did()
        with patch("routes.dialogs.user_repo.get_user", new=AsyncMock(return_value=user)), \
             patch("routes.dialogs.dialog_repo.ensure_active_dialog",
                   new=AsyncMock(return_value=did)), \
             patch("routes.dialogs.dialog_repo.get_dialog_messages",
                   new=AsyncMock(return_value=[])):
            resp = api_client.post(f"/dialogs/{user.id}/ensure")
        assert resp.status_code == 200
        assert resp.json()["messages"] == []

# GET /{user_id}/messages

class TestGetMessages:

    @pytest.mark.api
    def test_no_params_returns_messages_by_mode(self, api_client) -> None:
        uid = _uid()
        by_mode = {"assistant": _fake_messages(), "artist": _fake_messages(1)}

        with patch("routes.dialogs.dialog_repo.get_dialog_messages_by_mode",
                   new=AsyncMock(return_value=by_mode)):
            resp = api_client.get(f"/dialogs/{uid}/messages")

        assert resp.status_code == 200
        assert resp.json()["messages_by_mode"] == by_mode

    @pytest.mark.api
    def test_no_params_value_error_returns_404(self, api_client) -> None:
        uid = _uid()
        with patch("routes.dialogs.dialog_repo.get_dialog_messages_by_mode",
                   new=AsyncMock(side_effect=ValueError("User not found"))):
            resp = api_client.get(f"/dialogs/{uid}/messages")
        assert resp.status_code == 404

    @pytest.mark.api
    def test_with_dialog_id_returns_messages(self, api_client) -> None:
        uid = _uid()
        did = _did()
        msgs = _fake_messages(fake.random_int(min=1, max=5))

        with patch("routes.dialogs.dialog_repo.get_dialog_messages",
                   new=AsyncMock(return_value=msgs)):
            resp = api_client.get(f"/dialogs/{uid}/messages", params={"dialog_id": did})

        assert resp.status_code == 200
        assert resp.json()["messages"] == msgs

    @pytest.mark.api
    def test_with_chat_mode_resolves_dialog_id(self, api_client, user_factory) -> None:
        user = user_factory()
        did = _did()
        import types
        user_obj = types.SimpleNamespace(**vars(user), current_dialog_ids={"artist": did})
        msgs = _fake_messages(2)

        with patch("routes.dialogs.user_repo.get_user", new=AsyncMock(return_value=user_obj)), \
             patch("routes.dialogs.dialog_repo.get_dialog_messages",
                   new=AsyncMock(return_value=msgs)):
            resp = api_client.get(
                f"/dialogs/{user.id}/messages",
                params={"chat_mode": "artist"},
            )

        assert resp.status_code == 200
        assert resp.json()["messages"] == msgs

    @pytest.mark.api
    def test_with_chat_mode_user_not_found_returns_404(self, api_client) -> None:
        uid = _uid()
        with patch("routes.dialogs.user_repo.get_user", new=AsyncMock(return_value=None)):
            resp = api_client.get(f"/dialogs/{uid}/messages",
                                  params={"chat_mode": "assistant"})
        assert resp.status_code == 404

    @pytest.mark.api
    def test_faker_messages_round_trip(self, api_client) -> None:
        uid = _uid()
        did = _did()
        msgs = _fake_messages(fake.random_int(min=2, max=8))

        with patch("routes.dialogs.dialog_repo.get_dialog_messages",
                   new=AsyncMock(return_value=msgs)):
            resp = api_client.get(f"/dialogs/{uid}/messages", params={"dialog_id": did})

        assert resp.json()["messages"] == msgs

# POST /{user_id}/pop-last

class TestPopLastExchange:

    @pytest.mark.api
    def test_pop_last_returns_removed_user_message(self, api_client) -> None:
        uid = _uid()
        did = _did()
        removed = {"id": "msg_1", "role": "user", "content": "вопрос"}

        with patch("routes.dialogs.dialog_repo.delete_last_exchange",
                   new=AsyncMock(return_value=removed)):
            resp = api_client.post(f"/dialogs/{uid}/pop-last", params={"dialog_id": did})

        assert resp.status_code == 200
        assert resp.json()["message"] == removed

    @pytest.mark.api
    def test_pop_last_empty_dialog_returns_none(self, api_client) -> None:
        uid = _uid()
        did = _did()
        with patch("routes.dialogs.dialog_repo.delete_last_exchange",
                   new=AsyncMock(return_value=None)):
            resp = api_client.post(f"/dialogs/{uid}/pop-last", params={"dialog_id": did})
        assert resp.status_code == 200
        assert resp.json()["message"] is None

    @pytest.mark.api
    def test_pop_last_without_dialog_resolves_current(self, api_client) -> None:
        uid = _uid()
        user = MagicMock()
        user.state.current_dialog_id = _did()
        with patch("routes.dialogs.user_repo.get_user", new=AsyncMock(return_value=user)), \
             patch("routes.dialogs.dialog_repo.delete_last_exchange",
                   new=AsyncMock(return_value=None)) as mock_del:
            resp = api_client.post(f"/dialogs/{uid}/pop-last")
        assert resp.status_code == 200
        mock_del.assert_awaited_once()

# POST /{user_id}/exchange

class TestAppendExchange:

    @pytest.mark.api
    def test_exchange_appends_canonical_pair(self, api_client) -> None:
        uid = _uid()
        did = _did()

        with patch("routes.dialogs.dialog_repo.append_messages",
                   new=AsyncMock(return_value=True)) as mock_append:
            resp = api_client.post(
                f"/dialogs/{uid}/exchange",
                json={"dialog_id": did, "user": "промпт", "bot": "https://img", "model": "gpt-image-1.5"},
            )

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert mock_append.await_args is not None
        msgs = mock_append.await_args.args[3]
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert msgs[1]["parent_id"] == msgs[0]["id"]
        assert msgs[1]["model"] == "gpt-image-1.5"

    @pytest.mark.api
    def test_exchange_without_dialog_id_ensures_active(self, api_client) -> None:
        uid = _uid()
        with patch("routes.dialogs.dialog_repo.ensure_active_dialog",
                   new=AsyncMock(return_value=_did())) as mock_ensure, \
             patch("routes.dialogs.dialog_repo.append_messages",
                   new=AsyncMock(return_value=True)):
            resp = api_client.post(
                f"/dialogs/{uid}/exchange",
                json={"user": "q", "bot": "a"},
            )
        assert resp.status_code == 200
        mock_ensure.assert_awaited_once()

# GET /{user_id}/message-count

class TestMessageCount:

    @pytest.mark.api
    def test_message_count_returns_count(self, api_client) -> None:
        uid = _uid()
        count = fake.random_int(min=0, max=10_000)

        with patch("routes.dialogs.dialog_repo.get_user_message_count",
                   new=AsyncMock(return_value=count)):
            resp = api_client.get(f"/dialogs/{uid}/message-count")

        assert resp.status_code == 200
        assert resp.json()["count"] == count

    @pytest.mark.api
    def test_message_count_zero(self, api_client) -> None:
        uid = _uid()
        with patch("routes.dialogs.dialog_repo.get_user_message_count",
                   new=AsyncMock(return_value=0)):
            resp = api_client.get(f"/dialogs/{uid}/message-count")
        assert resp.json()["count"] == 0

    @pytest.mark.api
    def test_faker_batch_message_counts(self, api_client) -> None:
        for _ in range(3):
            uid = _uid()
            count = fake.random_int(min=1, max=5000)
            with patch("routes.dialogs.dialog_repo.get_user_message_count",
                       new=AsyncMock(return_value=count)):
                resp = api_client.get(f"/dialogs/{uid}/message-count")
            assert resp.json()["count"] == count
