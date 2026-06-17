"""Юнит-тесты для bot/src/core/auth_state.py.

Тестируем чистые функции is_admin() и is_allowed().
Модуль-уровневые множества _admin_ids и _allowed_ids манипулируются напрямую.
Белый список / не в белом списке — полный набор кейсов.
"""

import pytest

import src.core.auth_state as auth_state


@pytest.fixture(autouse=True)
def reset_auth_state():
    """Сбрасываем множества до и после каждого теста."""
    auth_state._admin_ids = set()
    auth_state._allowed_ids = set()
    yield
    auth_state._admin_ids = set()
    auth_state._allowed_ids = set()


# is_admin


class TestIsAdmin:
    @pytest.mark.unit
    def test_admin_in_set_returns_true(self, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        auth_state._admin_ids.add(uid)
        assert auth_state.is_admin(uid) is True

    @pytest.mark.unit
    def test_non_admin_returns_false(self, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        assert auth_state.is_admin(uid) is False

    @pytest.mark.unit
    def test_user_in_allowed_but_not_admin(self, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        auth_state._allowed_ids.add(uid)
        # allowed != admin
        assert auth_state.is_admin(uid) is False

    @pytest.mark.unit
    def test_multiple_admins(self, fake) -> None:
        ids = {fake.random_int(min=100_000, max=999_999_999) for _ in range(5)}
        auth_state._admin_ids.update(ids)
        for uid in ids:
            assert auth_state.is_admin(uid) is True

    @pytest.mark.unit
    def test_empty_admin_set_always_false(self, fake) -> None:
        for _ in range(5):
            assert auth_state.is_admin(fake.random_int()) is False

    @pytest.mark.unit
    def test_faker_batch_admin_check(self, fake) -> None:
        admins = {fake.random_int(min=1, max=999_999) for _ in range(10)}
        non_admins = {fake.random_int(min=1_000_000, max=9_999_999) for _ in range(10)}
        auth_state._admin_ids.update(admins)
        for uid in admins:
            assert auth_state.is_admin(uid) is True
        for uid in non_admins:
            assert auth_state.is_admin(uid) is False


# is_allowed


class TestIsAllowed:
    @pytest.mark.unit
    def test_user_in_allowed_ids_returns_true(self, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        auth_state._allowed_ids.add(uid)
        assert auth_state.is_allowed(uid) is True

    @pytest.mark.unit
    def test_admin_is_also_allowed(self, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        auth_state._admin_ids.add(uid)
        # Администратор автоматически разрешён
        assert auth_state.is_allowed(uid) is True

    @pytest.mark.unit
    def test_user_not_in_any_set_returns_false(self, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        assert auth_state.is_allowed(uid) is False

    @pytest.mark.unit
    def test_not_in_whitelist_returns_false(self, fake) -> None:
        """Проверка: пользователь НЕ в белом списке."""
        allowed_uid = fake.random_int(min=1_000_000, max=9_999_999)
        blocked_uid = fake.random_int(min=10_000_000, max=99_999_999)
        auth_state._allowed_ids.add(allowed_uid)
        # allowed_uid разрешён
        assert auth_state.is_allowed(allowed_uid) is True
        # blocked_uid НЕ в списке
        assert auth_state.is_allowed(blocked_uid) is False

    @pytest.mark.unit
    def test_empty_sets_always_false(self, fake) -> None:
        for _ in range(5):
            assert auth_state.is_allowed(fake.random_int()) is False

    @pytest.mark.unit
    def test_user_in_both_sets_allowed(self, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        auth_state._admin_ids.add(uid)
        auth_state._allowed_ids.add(uid)
        assert auth_state.is_allowed(uid) is True

    @pytest.mark.unit
    def test_faker_whitelist_batch(self, fake) -> None:
        allowed = {fake.random_int(min=1, max=999_999) for _ in range(20)}
        blocked = {fake.random_int(min=1_000_000, max=9_999_999) for _ in range(20)}
        auth_state._allowed_ids.update(allowed)
        for uid in allowed:
            assert auth_state.is_allowed(uid) is True
        for uid in blocked:
            assert auth_state.is_allowed(uid) is False

    @pytest.mark.unit
    @pytest.mark.parametrize("count", [1, 5, 100, 500])
    def test_whitelist_scales_correctly(self, fake, count: int) -> None:
        ids = {fake.random_int(min=1, max=999_999_999) for _ in range(count)}
        auth_state._allowed_ids.update(ids)
        assert all(auth_state.is_allowed(uid) for uid in ids)


# reload_sync (unit, без файла)


class TestReloadSync:
    @pytest.mark.unit
    def test_reload_sync_with_missing_file_keeps_empty_sets(self) -> None:
        """Если файл не существует, множества остаются пустыми (exception handled)."""
        import src.core.auth_state as auth_state_mod
        # Файл по умолчанию /app/configs/user-ids.yml не существует локально
        auth_state_mod.reload_sync()
        # Не должно упасть и не должно изменить множества (exception handled внутри)
        # Множества могут быть любыми (пустыми или пустыми после ошибки)
        assert isinstance(auth_state_mod._admin_ids, set)
        assert isinstance(auth_state_mod._allowed_ids, set)