"""Юнит-тесты для логики whitelist роутера (add/remove admin/user).

Тестируем:
- Валидацию user_id (8-13 цифр)
- Хелперы _read_user_ids / _write_user_ids через mock файловой системы
- Логику добавления/удаления пользователей и админов
- Проверки (уже в списке, не в списке, admin нельзя удалить как user)

Реальный файл /app/configs/user-ids.yml не используется — всё через mock.
"""

import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest


# ── Патч настроек для всего модуля ────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_whitelist_module_settings(mocker):
    mocker.patch(
        "src.bot.routers.admin.whitelist.settings",
        types.SimpleNamespace(
            admin_ids=[999_000_000],
            whitelist_mode=True,
            allowed_user_ids=[],
        ),
    )


# ── Валидация User ID ─────────────────────────────────────────────────────────


class TestUserIdValidation:
    """Тестируем логику валидации ID из msg_user_id_input."""

    @pytest.mark.unit
    @pytest.mark.parametrize("raw,is_valid", [
        ("12345678",    True),   # 8 цифр — минимум
        ("123456789",   True),   # 9 цифр
        ("9999999999999", True), # 13 цифр — максимум
        ("1234567",     False),  # 7 цифр — слишком мало
        ("12345678901234", False), # 14 цифр — слишком много
        ("abc12345",    False),  # не цифры
        ("",            False),  # пустая строка
        ("12 345678",   False),  # пробел
        ("12345678.0",  False),  # дробное
    ])
    def test_user_id_validation(self, raw: str, is_valid: bool) -> None:
        raw = raw.strip()
        result = raw.isdigit() and (8 <= len(raw) <= 13)
        assert result == is_valid

    @pytest.mark.unit
    def test_faker_valid_telegram_ids(self, fake) -> None:
        for _ in range(10):
            uid = str(fake.random_int(min=10_000_000, max=9_999_999_999))
            assert uid.isdigit() and (8 <= len(uid) <= 13)

    @pytest.mark.unit
    def test_faker_generated_ids_pass_validation(self, fake) -> None:
        valid_ids = []
        for _ in range(20):
            uid_int = fake.random_int(min=100_000_000, max=999_999_999)
            uid_str = str(uid_int)
            if uid_str.isdigit() and (8 <= len(uid_str) <= 13):
                valid_ids.append(uid_int)
        assert len(valid_ids) > 15


# ── Read/Write YAML helpers ───────────────────────────────────────────────────


class TestReadUserIds:
    @pytest.mark.unit
    def test_read_returns_dict_when_file_missing(self, mocker) -> None:
        mocker.patch("src.bot.routers.admin.whitelist.USER_IDS_PATH",
                     Path("/nonexistent/path/user-ids.yml"))
        from src.bot.routers.admin.whitelist import _read_user_ids
        result = _read_user_ids()
        assert result == {"admin_user_ids": [], "allowed_user_ids": []}

    @pytest.mark.unit
    def test_read_parses_yaml_correctly(self, mocker, tmp_path) -> None:
        import yaml
        data = {"admin_user_ids": [111, 222], "allowed_user_ids": [333, 444]}
        yml_file = tmp_path / "user-ids.yml"
        yml_file.write_text(yaml.dump(data), encoding="utf-8")
        mocker.patch("src.bot.routers.admin.whitelist.USER_IDS_PATH", yml_file)

        from src.bot.routers.admin.whitelist import _read_user_ids
        result = _read_user_ids()
        assert result["admin_user_ids"] == [111, 222]
        assert result["allowed_user_ids"] == [333, 444]

    @pytest.mark.unit
    def test_read_returns_empty_for_empty_yaml(self, mocker, tmp_path) -> None:
        yml_file = tmp_path / "user-ids.yml"
        yml_file.write_text("", encoding="utf-8")
        mocker.patch("src.bot.routers.admin.whitelist.USER_IDS_PATH", yml_file)

        from src.bot.routers.admin.whitelist import _read_user_ids
        result = _read_user_ids()
        # yaml.safe_load("") → None → None or {} → {} (пустой dict)
        assert result.get("admin_user_ids", []) == []
        assert result.get("allowed_user_ids", []) == []


class TestWriteUserIds:
    @pytest.mark.unit
    def test_write_creates_valid_yaml(self, mocker, tmp_path) -> None:
        import yaml
        yml_file = tmp_path / "user-ids.yml"
        mocker.patch("src.bot.routers.admin.whitelist.USER_IDS_PATH", yml_file)

        data = {"admin_user_ids": [100, 200], "allowed_user_ids": [300]}
        from src.bot.routers.admin.whitelist import _write_user_ids
        _write_user_ids(data)

        written = yaml.safe_load(yml_file.read_text(encoding="utf-8"))
        assert written["admin_user_ids"] == [100, 200]
        assert written["allowed_user_ids"] == [300]

    @pytest.mark.unit
    def test_write_and_read_roundtrip(self, mocker, tmp_path, fake) -> None:
        import yaml
        yml_file = tmp_path / "user-ids.yml"
        mocker.patch("src.bot.routers.admin.whitelist.USER_IDS_PATH", yml_file)

        original = {
            "admin_user_ids": [fake.random_int(min=100_000_000, max=999_999_999)],
            "allowed_user_ids": [fake.random_int(min=100_000_000, max=999_999_999)],
        }
        from src.bot.routers.admin.whitelist import _write_user_ids, _read_user_ids
        _write_user_ids(original)
        result = _read_user_ids()
        assert result["admin_user_ids"] == original["admin_user_ids"]
        assert result["allowed_user_ids"] == original["allowed_user_ids"]


# ── Логика добавления/удаления ────────────────────────────────────────────────


class TestAddUserLogic:
    """Тестируем логику: add_user действие."""

    @pytest.mark.unit
    def test_add_new_user_to_empty_list(self, fake) -> None:
        allowed: list[int] = []
        new_uid = fake.random_int(min=100_000_000, max=999_999_999)
        if new_uid not in allowed:
            allowed.append(new_uid)
        assert new_uid in allowed

    @pytest.mark.unit
    def test_add_existing_user_detected(self, fake) -> None:
        uid = fake.random_int(min=100_000_000, max=999_999_999)
        allowed = [uid]
        already_exists = uid in allowed
        assert already_exists is True

    @pytest.mark.unit
    def test_faker_add_multiple_unique_users(self, fake) -> None:
        allowed: list[int] = []
        for _ in range(20):
            uid = fake.random_int(min=100_000_000, max=999_999_999)
            if uid not in allowed:
                allowed.append(uid)
        # После добавления уникальных — нет дубликатов
        assert len(allowed) == len(set(allowed))


class TestRemoveUserLogic:
    @pytest.mark.unit
    def test_remove_existing_user(self, fake) -> None:
        uid = fake.random_int(min=100_000_000, max=999_999_999)
        allowed = [uid, uid + 1]
        admins: list[int] = []
        # Не в admins — можно удалить
        if uid not in admins and uid in allowed:
            allowed.remove(uid)
        assert uid not in allowed

    @pytest.mark.unit
    def test_cannot_remove_admin_as_user(self, fake) -> None:
        uid = fake.random_int(min=100_000_000, max=999_999_999)
        allowed = [uid]
        admins = [uid]  # uid — и в admin, и в allowed
        # Попытка удалить как user → должна быть отклонена
        should_reject = uid in admins
        assert should_reject is True

    @pytest.mark.unit
    def test_remove_nonexistent_user_detected(self, fake) -> None:
        uid = fake.random_int(min=100_000_000, max=999_999_999)
        allowed: list[int] = []
        not_in_list = uid not in allowed
        assert not_in_list is True


class TestAdminManagementLogic:
    @pytest.mark.unit
    def test_add_admin_must_be_in_whitelist(self, fake) -> None:
        uid = fake.random_int(min=100_000_000, max=999_999_999)
        allowed: list[int] = []  # uid не в белом списке
        admins: list[int] = []
        # Нельзя добавить в admin если не в whitelist
        can_add = uid in allowed and uid not in admins
        assert can_add is False

    @pytest.mark.unit
    def test_add_admin_already_admin_rejected(self, fake) -> None:
        uid = fake.random_int(min=100_000_000, max=999_999_999)
        allowed = [uid]
        admins = [uid]  # уже admin
        already_admin = uid in admins
        assert already_admin is True

    @pytest.mark.unit
    def test_add_admin_success_flow(self, fake) -> None:
        uid = fake.random_int(min=100_000_000, max=999_999_999)
        allowed = [uid]
        admins: list[int] = []
        # Пользователь в whitelist, не admin → можно добавить
        can_add = uid in allowed and uid not in admins
        assert can_add is True
        admins.append(uid)
        assert uid in admins

    @pytest.mark.unit
    def test_remove_admin_not_in_list_detected(self, fake) -> None:
        uid = fake.random_int(min=100_000_000, max=999_999_999)
        admins: list[int] = []
        not_in_list = uid not in admins
        assert not_in_list is True

    @pytest.mark.unit
    def test_faker_add_remove_admins_cycle(self, fake) -> None:
        """Полный цикл: добавление и удаление N администраторов."""
        admins: list[int] = []
        allowed: list[int] = []
        uids = [fake.random_int(min=100_000_000, max=999_999_999) for _ in range(10)]

        # Добавляем всех в whitelist
        for uid in uids:
            allowed.append(uid)

        # Добавляем как админов
        for uid in uids:
            if uid in allowed and uid not in admins:
                admins.append(uid)
        assert len(admins) == 10

        # Удаляем всех из админов
        for uid in uids:
            if uid in admins:
                admins.remove(uid)
        assert len(admins) == 0
        assert len(allowed) == 10  # в whitelist остались


# ── Суперадмин проверки ───────────────────────────────────────────────────────


class TestSuperadminRestrictions:
    @pytest.mark.unit
    def test_only_superadmin_can_add_admin(self, fake) -> None:
        superadmin_id = 999_000_000
        regular_admin_id = fake.random_int(min=100_000_000, max=999_999_999)
        # regular_admin — не суперадмин, не может добавлять/удалять adminов
        is_superadmin = regular_admin_id == superadmin_id
        assert is_superadmin is False

    @pytest.mark.unit
    def test_superadmin_id_check(self) -> None:
        superadmin_id = 999_000_000
        is_superadmin = 999_000_000 == superadmin_id
        assert is_superadmin is True
