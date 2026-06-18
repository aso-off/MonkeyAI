"""In-memory TTL-кэш профиля пользователя — срезает HTTP к API на частых сообщениях."""
import time

_store: dict[int, tuple[float, object]] = {}
_monotonic = time.monotonic  # подменяется в тестах


def get(user_id: int):
    item = _store.get(user_id)
    if item is None:
        return None
    expires_at, value = item
    if _monotonic() >= expires_at:
        _store.pop(user_id, None)
        return None
    return value


def put(user_id: int, value, ttl_seconds: float) -> None:
    if ttl_seconds <= 0:
        return
    _store[user_id] = (_monotonic() + ttl_seconds, value)


def invalidate(user_id: int) -> None:
    _store.pop(user_id, None)


def clear() -> None:
    _store.clear()
