import hashlib
import hmac
import json
import os
import time

from faker import Faker
from locust import HttpUser, between, events, task

fake = Faker()

_BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN", "123456:e2e-token")
_SERVICE_TOKEN = os.environ.get("API_SERVICE_TOKEN", "e2e-service-token")
_MODEL = os.environ.get("LOAD_MODEL", "gpt-5.4-nano")
_BASE_URL = os.environ.get("LOAD_BASE_URL", "http://localhost:8000")


def _make_init_data(user_id: int) -> str:
    # валидная telegram-init-data под тестовый токен
    user = json.dumps(
        {"id": user_id, "first_name": fake.first_name(), "username": fake.user_name()},
        separators=(",", ":"),
    )
    params = {"auth_date": str(int(time.time())), "user": user, "query_id": fake.uuid4()}
    data_check = "\n".join(f"{k}={params[k]}" for k in sorted(params))
    secret = hmac.new(b"WebAppData", _BOT_TOKEN.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return "&".join(f"{k}={v}" for k, v in params.items())


class MonkeyUser(HttpUser):
    host = _BASE_URL
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.user_id = fake.random_int(min=10_000_000, max=99_999_999)
        self._tma = {"Authorization": f"tma {_make_init_data(self.user_id)}"}
        self._svc = {"Authorization": f"Bearer {_SERVICE_TOKEN}"}

    @task(1)
    def health(self) -> None:
        self.client.get("/health", name="GET /health")

    @task(3)
    def webapp_me(self) -> None:
        self.client.get("/webapp/me", headers=self._tma, name="GET /webapp/me")

    @task(3)
    def webapp_dialogs(self) -> None:
        self.client.get("/webapp/dialogs", headers=self._tma, name="GET /webapp/dialogs")

    @task(4)
    def chat_complete(self) -> None:
        body = {
            "user_id": self.user_id,
            "message": fake.sentence(nb_words=8),
            "model": _MODEL,
            "chat_mode": "assistant",
        }
        self.client.post("/chat/complete", json=body, headers=self._svc, name="POST /chat/complete")

    @task(1)
    def chat_stream(self) -> None:
        body = {
            "user_id": self.user_id,
            "message": fake.sentence(nb_words=8),
            "model": _MODEL,
            "chat_mode": "assistant",
        }
        with self.client.post(
            "/chat/stream", json=body, headers=self._svc,
            stream=True, name="POST /chat/stream", catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"status {resp.status_code}")
                return
            for _ in resp.iter_lines():
                pass
            resp.success()


@events.quitting.add_listener
def _enforce_gates(environment, **_kwargs) -> None:
    # ненулевой exit-code при превышении порогов (если заданы в env)
    stats = environment.runner.stats.total if environment.runner else None
    if stats is None:
        return

    max_fail = os.environ.get("LOAD_MAX_FAIL_RATIO")
    if max_fail is not None and stats.fail_ratio > float(max_fail):
        print(f"GATE FAILED: fail_ratio {stats.fail_ratio:.4f} > {max_fail}")
        environment.process_exit_code = 1

    max_p95 = os.environ.get("LOAD_MAX_P95_MS")
    if max_p95 is not None and stats.get_response_time_percentile(0.95) > float(max_p95):
        print(f"GATE FAILED: p95 {stats.get_response_time_percentile(0.95)}ms > {max_p95}ms")
        environment.process_exit_code = 1
