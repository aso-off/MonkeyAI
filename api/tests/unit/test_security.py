"""Юнит-тесты для api/src/core/security.py — функция _verify_init_data.

Загружаем РЕАЛЬНЫЙ модуль через importlib (не stub из conftest).
"""

import hashlib
import hmac
import importlib.util
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest

# Загрузка реального модуля

_SECURITY_PATH = Path(__file__).resolve().parents[2] / "src" / "core" / "security.py"
_sec_spec = importlib.util.spec_from_file_location("_real_core_security", _SECURITY_PATH)
assert _sec_spec and _sec_spec.loader
_sec_mod = importlib.util.module_from_spec(_sec_spec)
_sec_spec.loader.exec_module(_sec_mod)

_verify_init_data = _sec_mod._verify_init_data

# Helpers

_BOT_TOKEN = "1234567890:AABBCCDDEEFFaabbccddeeff00112233445"


def _make_init_data(
    bot_token: str = _BOT_TOKEN,
    user_id: int = 123456789,
    auth_date: int | None = None,
    extra_params: dict | None = None,
) -> str:
    """Генерирует корректный Telegram initData с валидным HMAC."""
    if auth_date is None:
        auth_date = int(time.time())
    params: dict[str, str] = {
        "user": f'{{"id":{user_id},"first_name":"Test"}}',
        "auth_date": str(auth_date),
    }
    if extra_params:
        params.update(extra_params)
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    hash_ = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**params, "hash": hash_})


# Тесты


class TestVerifyInitDataValid:
    @pytest.mark.unit
    @pytest.mark.security
    def test_valid_data_returns_dict(self) -> None:
        result = _verify_init_data(_make_init_data(), _BOT_TOKEN)
        assert isinstance(result, dict)
        assert "user" in result and "auth_date" in result

    @pytest.mark.unit
    @pytest.mark.security
    def test_returned_dict_excludes_hash(self) -> None:
        assert "hash" not in _verify_init_data(_make_init_data(), _BOT_TOKEN)

    @pytest.mark.unit
    @pytest.mark.security
    def test_valid_with_extra_params(self) -> None:
        init_data = _make_init_data(extra_params={"chat_instance": "-12345"})
        assert "chat_instance" in _verify_init_data(init_data, _BOT_TOKEN)

    @pytest.mark.unit
    @pytest.mark.security
    def test_faker_user_ids_all_valid(self, fake) -> None:
        for _ in range(5):
            uid = fake.random_int(min=100_000, max=999_999_999)
            result = _verify_init_data(_make_init_data(user_id=uid), _BOT_TOKEN)
            assert str(uid) in result.get("user", "")

    @pytest.mark.unit
    @pytest.mark.security
    def test_custom_max_age_accepts_fresh_data(self) -> None:
        assert isinstance(_verify_init_data(_make_init_data(), _BOT_TOKEN, max_age_seconds=86400), dict)


class TestVerifyInitDataMissingFields:
    @pytest.mark.unit
    @pytest.mark.security
    def test_missing_hash_raises(self) -> None:
        init_data = urlencode({"user": '{"id":123}', "auth_date": str(int(time.time()))})
        with pytest.raises(ValueError, match="hash missing"):
            _verify_init_data(init_data, _BOT_TOKEN)

    @pytest.mark.unit
    @pytest.mark.security
    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="hash missing"):
            _verify_init_data("", _BOT_TOKEN)

    @pytest.mark.unit
    @pytest.mark.security
    def test_missing_auth_date_raises(self) -> None:
        params = {"user": '{"id":123}'}
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
        secret = hmac.new(b"WebAppData", _BOT_TOKEN.encode(), hashlib.sha256).digest()
        hash_ = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        with pytest.raises(ValueError, match="auth_date missing"):
            _verify_init_data(urlencode({**params, "hash": hash_}), _BOT_TOKEN)


class TestVerifyInitDataExpiry:
    @pytest.mark.unit
    @pytest.mark.security
    def test_expired_2h_raises(self) -> None:
        with pytest.raises(ValueError, match="expired"):
            _verify_init_data(_make_init_data(auth_date=int(time.time()) - 7200), _BOT_TOKEN)

    @pytest.mark.unit
    @pytest.mark.security
    def test_just_expired_raises(self) -> None:
        with pytest.raises(ValueError, match="expired"):
            _verify_init_data(_make_init_data(auth_date=int(time.time()) - 3601), _BOT_TOKEN)

    @pytest.mark.unit
    @pytest.mark.security
    def test_custom_max_age_rejects(self) -> None:
        init_data = _make_init_data(auth_date=int(time.time()) - 600)
        with pytest.raises(ValueError, match="expired"):
            _verify_init_data(init_data, _BOT_TOKEN, max_age_seconds=300)

    @pytest.mark.unit
    @pytest.mark.security
    def test_custom_max_age_accepts(self) -> None:
        init_data = _make_init_data(auth_date=int(time.time()) - 600)
        assert isinstance(_verify_init_data(init_data, _BOT_TOKEN, max_age_seconds=3600), dict)


class TestVerifyInitDataWrongHash:
    @pytest.mark.unit
    @pytest.mark.security
    def test_wrong_hash_raises(self) -> None:
        tampered = _make_init_data().rsplit("hash=", 1)[0] + "hash=" + "a" * 64
        with pytest.raises(ValueError, match="invalid hash"):
            _verify_init_data(tampered, _BOT_TOKEN)

    @pytest.mark.unit
    @pytest.mark.security
    def test_wrong_token_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid hash"):
            _verify_init_data(_make_init_data(), "other_token:AABBCCDD")

    @pytest.mark.unit
    @pytest.mark.security
    def test_tampered_user_raises(self) -> None:
        tampered = _make_init_data(user_id=111).replace("111", "999")
        with pytest.raises(ValueError, match="invalid hash"):
            _verify_init_data(tampered, _BOT_TOKEN)

    @pytest.mark.unit
    @pytest.mark.security
    def test_faker_random_data_raises(self, fake) -> None:
        random_data = f"user=%7B%22id%22%3A{fake.random_int()}%7D&auth_date={int(time.time())}&hash={'x'*64}"
        with pytest.raises(ValueError):
            _verify_init_data(random_data, _BOT_TOKEN)


class TestVerifyInitDataHmacCorrectness:
    @pytest.mark.unit
    @pytest.mark.security
    def test_different_tokens_different_hashes(self) -> None:
        ts = int(time.time())
        d1 = _make_init_data(bot_token="token1:AAAA", auth_date=ts)
        d2 = _make_init_data(bot_token="token2:BBBB", auth_date=ts)
        h1 = dict(p.split("=", 1) for p in d1.split("&")).get("hash", "")
        h2 = dict(p.split("=", 1) for p in d2.split("&")).get("hash", "")
        assert h1 != h2

    @pytest.mark.unit
    @pytest.mark.security
    @pytest.mark.parametrize("user_id", [1, 100_000, 999_999_999, 5_000_000_000])
    def test_various_user_ids_pass(self, user_id: int) -> None:
        assert isinstance(_verify_init_data(_make_init_data(user_id=user_id), _BOT_TOKEN), dict)