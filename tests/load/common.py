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
_BASE_URL = os.environ.get("LOAD_BASE_URL", "http://localhost:8000")

_MODELS = ["gpt-5.4-nano", "gpt-4o", "gpt-5.4-mini"]
_THEMES = ["light", "dark", "system"]
_LANGS = ["ru", "en"]

_POOL_SIZE = int(os.environ.get("LOAD_USER_POOL", "200"))
_SEEDED_USERS: list[int] = []


@events.test_start.add_listener
def _seed_pool(environment, **_kwargs) -> None:
    # пул whitelisted-юзеров создаётся один раз до нагрузки (а не в on_start каждого)
    import requests

    svc = {"Authorization": f"Bearer {_SERVICE_TOKEN}"}
    s = requests.Session()
    for _ in range(_POOL_SIZE):
        uid = fake.random_int(min=10_000_000, max=99_999_999)
        try:
            s.post(f"{_BASE_URL}/users", json={"id": uid, "chat_id": uid, "first_name": "Load"},
                   headers=svc, timeout=10)
            s.patch(f"{_BASE_URL}/users/{uid}", json={"is_whitelisted": True}, headers=svc, timeout=10)
            _SEEDED_USERS.append(uid)
        except Exception:
            pass
    print(f"[load] pre-seeded {len(_SEEDED_USERS)} whitelisted users")


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
    wait_time = between(0.5, 5)  # рваный ритм — у каждого юзера свой

    def on_start(self) -> None:
        # берём готового whitelisted-юзера из пула (несколько сессий на одного — реалистично)
        self.user_id = (
            fake.random_element(_SEEDED_USERS) if _SEEDED_USERS
            else fake.random_int(min=10_000_000, max=99_999_999)
        )
        self.model = fake.random_element(_MODELS)
        self._tma = {"Authorization": f"tma {_make_init_data(self.user_id)}"}
        self._svc = {"Authorization": f"Bearer {_SERVICE_TOKEN}"}
        self._dialog_id: str | None = None
        self._create_dialog()

    def _create_dialog(self) -> None:
        with self.client.post(
            "/webapp/dialogs/new", headers=self._tma,
            name="POST /webapp/dialogs/new", catch_response=True,
        ) as r:
            if r.status_code == 200:
                self._dialog_id = r.json().get("dialog_id")
                r.success()
            else:
                r.failure(f"status {r.status_code}")

    @task(1)
    def health(self) -> None:
        self.client.get("/health", name="GET /health")

    @task(3)
    def webapp_me(self) -> None:
        self.client.get("/webapp/me", headers=self._tma, name="GET /webapp/me")

    @task(3)
    def list_dialogs(self) -> None:
        self.client.get("/webapp/dialogs", headers=self._tma, name="GET /webapp/dialogs")

    @task(4)
    def webapp_chat(self) -> None:
        body = {"message": fake.sentence(nb_words=8), "chat_mode": "mini_app_assistant", "model": self.model}
        if self._dialog_id:
            body["dialog_id"] = self._dialog_id
        self.client.post("/webapp/chat", json=body, headers=self._tma, name="POST /webapp/chat")

    @task(2)
    def chat_complete(self) -> None:
        body = {"user_id": self.user_id, "message": fake.sentence(nb_words=8),
                "model": self.model, "chat_mode": "assistant"}
        self.client.post("/chat/complete", json=body, headers=self._svc, name="POST /chat/complete")

    @task(1)
    def chat_stream(self) -> None:
        body = {"user_id": self.user_id, "message": fake.sentence(nb_words=8),
                "model": self.model, "chat_mode": "assistant"}
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

    @task(2)
    def new_dialog(self) -> None:
        self._create_dialog()

    @task(1)
    def rename_dialog(self) -> None:
        if not self._dialog_id:
            return
        self.client.patch(
            f"/webapp/dialogs/{self._dialog_id}", json={"title": fake.sentence(nb_words=3)},
            headers=self._tma, name="PATCH /webapp/dialogs/[id]",
        )

    @task(1)
    def pin_dialog(self) -> None:
        if not self._dialog_id:
            return
        self.client.patch(
            f"/webapp/dialogs/{self._dialog_id}/pin", json={"pinned": fake.boolean()},
            headers=self._tma, name="PATCH /webapp/dialogs/[id]/pin",
        )

    @task(1)
    def delete_dialog(self) -> None:
        if not self._dialog_id:
            return
        with self.client.delete(
            f"/webapp/dialogs/{self._dialog_id}", headers=self._tma,
            name="DELETE /webapp/dialogs/[id]", catch_response=True,
        ) as r:
            if r.status_code in (204, 404):  # 404 = уже удалён, не ошибка
                r.success()
            else:
                r.failure(f"status {r.status_code}")
        self._dialog_id = None

    @task(2)
    def reaction(self) -> None:
        if not self._dialog_id:
            return
        body = {"reaction": fake.random_element(["like", "dislike"]),
                "model": self.model, "dialog_id": self._dialog_id}
        self.client.post("/webapp/reactions", json=body, headers=self._tma, name="POST /webapp/reactions")

    @task(2)
    def update_prefs(self) -> None:
        # «выбор модели»/темы/языка — сохранение префов (Redis + БД), без OpenAI
        self.model = fake.random_element(_MODELS)
        body = {"model": self.model, "theme": fake.random_element(_THEMES),
                "language": fake.random_element(_LANGS)}
        self.client.patch("/webapp/me", json=body, headers=self._tma, name="PATCH /webapp/me")


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
