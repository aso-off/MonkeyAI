"""Юнит-тесты для bot/src/schemas/user.py — Pydantic модели."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.user import UserCreate, UserRead, UserUpdate

# Helpers

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _valid_user_read_data(fake, **overrides) -> dict:
    return {
        "id": fake.random_int(min=100_000, max=999_999_999),
        "chat_id": fake.random_int(min=100_000, max=999_999_999),
        "username": fake.user_name(),
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "language": "ru",
        "first_seen": _now(),
        "last_interaction": _now(),
        "current_dialog_id": None,
        "current_chat_mode": "assistant",
        "current_model": "gpt-4o",
        "n_used_tokens": {"input": 100, "output": 50},
        "n_generated_images": 0,
        "n_transcribed_seconds": 0.0,
        **overrides,
    }

# UserCreate

class TestUserCreate:
    @pytest.mark.unit
    def test_minimal_valid(self, fake) -> None:
        user = UserCreate(
            id=fake.random_int(min=1, max=999_999_999),
            chat_id=fake.random_int(min=1, max=999_999_999),
        )
        assert user.first_name == ""
        assert user.language == "ru"
        assert user.username is None
        assert user.last_name is None

    @pytest.mark.unit
    def test_full_valid(self, fake) -> None:
        user = UserCreate(
            id=12345,
            chat_id=12345,
            username="testuser",
            first_name="Ivan",
            last_name="Petrov",
            language="en",
        )
        assert user.username == "testuser"
        assert user.first_name == "Ivan"
        assert user.language == "en"

    @pytest.mark.unit
    def test_missing_id_raises(self, fake) -> None:
        with pytest.raises(ValidationError):
            UserCreate(chat_id=fake.random_int())  # type: ignore[call-arg]  # намеренно без id

    @pytest.mark.unit
    def test_missing_chat_id_raises(self, fake) -> None:
        with pytest.raises(ValidationError):
            UserCreate(id=fake.random_int())  # type: ignore[call-arg]  # намеренно без chat_id

    @pytest.mark.unit
    def test_faker_batch_valid(self, fake) -> None:
        for _ in range(10):
            user = UserCreate(
                id=fake.random_int(min=1, max=999_999_999),
                chat_id=fake.random_int(min=1, max=999_999_999),
                username=fake.user_name(),
                first_name=fake.first_name(),
                language="ru",
            )
            assert isinstance(user.id, int)

    @pytest.mark.unit
    @pytest.mark.parametrize("lang", ["ru", "en", "de", "es", "fr", "pl", "pt", "tr", "system"])
    def test_language_field_accepts_string(self, lang: str, fake) -> None:
        user = UserCreate(id=1, chat_id=1, language=lang)
        assert user.language == lang

    @pytest.mark.unit
    def test_model_serialization(self, fake) -> None:
        user = UserCreate(id=42, chat_id=42, first_name="Test")
        data = user.model_dump()
        assert data["id"] == 42
        assert data["first_name"] == "Test"

# UserRead

class TestUserRead:
    @pytest.mark.unit
    def test_valid_full_data(self, fake) -> None:
        user = UserRead(**_valid_user_read_data(fake))
        assert isinstance(user.id, int)
        assert isinstance(user.n_used_tokens, dict)

    @pytest.mark.unit
    def test_username_optional(self, fake) -> None:
        data = _valid_user_read_data(fake, username=None)
        user = UserRead(**data)
        assert user.username is None

    @pytest.mark.unit
    def test_last_name_optional(self, fake) -> None:
        data = _valid_user_read_data(fake, last_name=None)
        user = UserRead(**data)
        assert user.last_name is None

    @pytest.mark.unit
    def test_current_dialog_id_optional(self, fake) -> None:
        data = _valid_user_read_data(fake, current_dialog_id=None)
        user = UserRead(**data)
        assert user.current_dialog_id is None

    @pytest.mark.unit
    def test_n_used_tokens_is_dict(self, fake) -> None:
        tokens = {"gpt-4o": {"input": 100, "output": 50}}
        user = UserRead(**_valid_user_read_data(fake, n_used_tokens=tokens))
        assert user.n_used_tokens == tokens

    @pytest.mark.unit
    def test_missing_required_field_raises(self, fake) -> None:
        data = _valid_user_read_data(fake)
        del data["first_name"]
        with pytest.raises(ValidationError):
            UserRead(**data)

    @pytest.mark.unit
    def test_json_serialization_roundtrip(self, fake) -> None:
        data = _valid_user_read_data(fake)
        user = UserRead(**data)
        json_str = user.model_dump_json()
        restored = UserRead.model_validate_json(json_str)
        assert restored.id == user.id

    @pytest.mark.unit
    def test_from_attributes_config(self, fake) -> None:
        # from_attributes=True позволяет создавать из объектов с атрибутами (ORM)
        class FakeOrm:
            pass

        data = _valid_user_read_data(fake)
        obj = FakeOrm()
        for k, v in data.items():
            setattr(obj, k, v)
        user = UserRead.model_validate(obj)
        assert user.id == data["id"]

    @pytest.mark.unit
    def test_faker_batch_valid(self, fake) -> None:
        for _ in range(5):
            user = UserRead(**_valid_user_read_data(fake))
            assert user.n_generated_images >= 0

# UserUpdate

class TestUserUpdate:
    @pytest.mark.unit
    def test_all_none_valid(self) -> None:
        update = UserUpdate()
        assert update.language is None
        assert update.current_chat_mode is None
        assert update.current_model is None
        assert update.current_dialog_id is None

    @pytest.mark.unit
    def test_partial_language_only(self) -> None:
        update = UserUpdate(language="en")
        assert update.language == "en"
        assert update.current_model is None

    @pytest.mark.unit
    def test_partial_model_only(self) -> None:
        update = UserUpdate(current_model="gpt-4o")
        assert update.current_model == "gpt-4o"
        assert update.language is None

    @pytest.mark.unit
    def test_partial_chat_mode(self) -> None:
        update = UserUpdate(current_chat_mode="code_assistant")
        assert update.current_chat_mode == "code_assistant"

    @pytest.mark.unit
    def test_partial_dialog_id(self) -> None:
        update = UserUpdate(current_dialog_id="dialog-uuid-123")
        assert update.current_dialog_id == "dialog-uuid-123"

    @pytest.mark.unit
    def test_model_dump_exclude_none(self) -> None:
        update = UserUpdate(language="de")
        dumped = update.model_dump(exclude_none=True)
        assert dumped == {"language": "de"}
        assert "current_model" not in dumped

    @pytest.mark.unit
    def test_model_dump_full(self) -> None:
        update = UserUpdate(language="fr", current_model="gpt-5.4-nano", current_chat_mode="assistant")
        dumped = update.model_dump(exclude_none=True)
        assert len(dumped) == 3

    @pytest.mark.unit
    def test_faker_batch(self, fake) -> None:
        langs = ["ru", "en", "de", "es"]
        for lang in langs:
            update = UserUpdate(language=lang)
            assert update.language == lang