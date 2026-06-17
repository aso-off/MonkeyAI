"""
Расширенные тесты для api/src/core/security.py.

Покрываем:
- verify_service_token — с токеном (match/no match), без токена
- _verify_init_data    — valid HMAC, missing hash, missing auth_date,
                         expired auth_date, invalid hash
- verify_webapp_init_data — через importlib (реальный модуль), tma prefix,
                            missing prefix, invalid initData

Faker: bot_token (sha256), auth_date, user ID, произвольные строки.
"""

import hashlib
import hmac
import importlib
import importlib.util
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

_SECURITY_FILE = Path(__file__).resolve().parents[2] / "src" / "core" / "security.py"

# Helpers

def _load_real_security() -> Any:
    """Загружаем реальный security.py через importlib, минуя stub из conftest."""
    spec = importlib.util.spec_from_file_location(
        f"_real_security_{fake.lexify('????')}", _SECURITY_FILE
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def _make_init_data(bot_token: str, user_id: int, max_age_seconds: int = 3600) -> str:
    """Генерируем валидный initData с корректным HMAC."""
    auth_date = str(int(time.time()))
    params = {
        "auth_date": auth_date,
        "user": f'{{"id":{user_id},"first_name":"Test"}}',
        "query_id": fake.lexify("AAAAAAAAA_???????????"),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    hash_value = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    params["hash"] = hash_value
    return "&".join(f"{k}={quote(str(v))}" for k, v in params.items())

# verify_service_token

class TestVerifyServiceToken:

    @pytest.mark.asyncio
    async def test_no_service_token_allows_all(self) -> None:
        """Если _SERVICE_TOKEN пустой — любой запрос проходит."""
        from unittest.mock import MagicMock

        # Загружаем реальный модуль с пустым токеном
        mod = _load_real_security()
        mod._SERVICE_TOKEN = ""

        credentials = MagicMock()
        credentials.credentials = fake.sha256()
        await mod.verify_service_token(credentials)  # не должен падать

    @pytest.mark.asyncio
    async def test_matching_token_passes(self) -> None:
        mod = _load_real_security()
        token = fake.sha256()[:32]
        mod._SERVICE_TOKEN = token

        from unittest.mock import MagicMock
        credentials = MagicMock()
        credentials.credentials = token
        await mod.verify_service_token(credentials)  # не должен падать

    @pytest.mark.asyncio
    async def test_wrong_token_raises_401(self) -> None:
        from fastapi import HTTPException
        mod = _load_real_security()
        mod._SERVICE_TOKEN = fake.sha256()[:32]

        from unittest.mock import MagicMock
        credentials = MagicMock()
        credentials.credentials = fake.sha256()[:32]  # другой токен

        with pytest.raises(HTTPException) as exc_info:
            await mod.verify_service_token(credentials)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_no_credentials_with_token_set_raises_401(self) -> None:
        from fastapi import HTTPException
        mod = _load_real_security()
        mod._SERVICE_TOKEN = fake.sha256()[:32]

        with pytest.raises(HTTPException) as exc_info:
            await mod.verify_service_token(None)
        assert exc_info.value.status_code == 401

# _verify_init_data

class TestVerifyInitData:

    @pytest.fixture(scope="class")
    def security_mod(self):
        return _load_real_security()

    def test_valid_init_data_returns_params(self, security_mod) -> None:
        bot_token = fake.sha256()[:40]
        uid = fake.random_int(min=100_000, max=999_999_999)
        init_data = _make_init_data(bot_token, uid)
        result = security_mod._verify_init_data(init_data, bot_token)
        assert "auth_date" in result
        assert "user" in result

    def test_missing_hash_raises_value_error(self, security_mod) -> None:
        init_data = f"auth_date={int(time.time())}&user=%7B%22id%22%3A123%7D"
        with pytest.raises(ValueError, match="hash missing"):
            security_mod._verify_init_data(init_data, fake.sha256()[:40])

    def test_missing_auth_date_raises_value_error(self, security_mod) -> None:
        bot_token = fake.sha256()[:40]
        params = {"user": '{"id":123}', "hash": "abc123"}
        init_data = "&".join(f"{k}={v}" for k, v in params.items())
        with pytest.raises(ValueError, match="auth_date missing"):
            security_mod._verify_init_data(init_data, bot_token)

    def test_expired_auth_date_raises_value_error(self, security_mod) -> None:
        bot_token = fake.sha256()[:40]
        # auth_date 2 часа назад
        old_ts = int(time.time()) - 7300
        params = {"auth_date": str(old_ts), "user": '{"id":123}'}
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        h = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        params["hash"] = h
        init_data = "&".join(f"{k}={v}" for k, v in params.items())

        with pytest.raises(ValueError, match="expired"):
            security_mod._verify_init_data(init_data, bot_token)

    def test_invalid_hash_raises_value_error(self, security_mod) -> None:
        bot_token = fake.sha256()[:40]
        uid = fake.random_int(min=100_000, max=999_999_999)
        init_data = _make_init_data(bot_token, uid)
        # Портим токен бота → HMAC будет неверным
        with pytest.raises(ValueError, match="invalid hash"):
            security_mod._verify_init_data(init_data, "wrong_" + bot_token)

    def test_faker_valid_users_all_pass(self, security_mod) -> None:
        bot_token = fake.sha256()[:40]
        for _ in range(3):
            uid = fake.random_int(min=100_000, max=999_999_999)
            init_data = _make_init_data(bot_token, uid)
            result = security_mod._verify_init_data(init_data, bot_token)
            assert "auth_date" in result

    def test_returns_dict_with_correct_user_id(self, security_mod) -> None:
        bot_token = fake.sha256()[:40]
        uid = fake.random_int(min=100_000, max=999_999_999)
        init_data = _make_init_data(bot_token, uid)
        result = security_mod._verify_init_data(init_data, bot_token)
        import json
        user = json.loads(result["user"])
        assert user["id"] == uid

# verify_webapp_init_data

class TestVerifyWebappInitData:

    @pytest.mark.asyncio
    async def test_missing_tma_prefix_raises_401(self) -> None:
        from fastapi import HTTPException
        mod = _load_real_security()

        from unittest.mock import MagicMock
        request = MagicMock()
        request.headers.get = MagicMock(return_value="Bearer some_token")

        with pytest.raises(HTTPException) as exc_info:
            await mod.verify_webapp_init_data(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_header_raises_401(self) -> None:
        from fastapi import HTTPException
        mod = _load_real_security()

        from unittest.mock import MagicMock
        request = MagicMock()
        request.headers.get = MagicMock(return_value="")

        with pytest.raises(HTTPException) as exc_info:
            await mod.verify_webapp_init_data(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_init_data_raises_401(self) -> None:
        from fastapi import HTTPException
        mod = _load_real_security()
        from unittest.mock import MagicMock

        request = MagicMock()
        request.headers.get = MagicMock(return_value="tma invalid_garbage_here")

        mock_settings = MagicMock()
        mock_settings.telegram_token.get_secret_value.return_value = fake.sha256()[:40]
        mod.settings = mock_settings

        with pytest.raises(HTTPException) as exc_info:
            await mod.verify_webapp_init_data(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_init_data_returns_dict(self) -> None:
        mod = _load_real_security()
        from unittest.mock import MagicMock

        bot_token = fake.sha256()[:40]
        uid = fake.random_int(min=100_000, max=999_999_999)
        init_data = _make_init_data(bot_token, uid)

        request = MagicMock()
        request.headers.get = MagicMock(return_value=f"tma {init_data}")

        mock_settings = MagicMock()
        mock_settings.telegram_token.get_secret_value.return_value = bot_token
        mod.settings = mock_settings

        result = await mod.verify_webapp_init_data(request)
        assert "auth_date" in result