from src.core import user_cache


def test_put_then_get_returns_value():
    user_cache.put(1, {"id": 1}, 60)
    assert user_cache.get(1) == {"id": 1}


def test_get_miss_returns_none():
    assert user_cache.get(999) is None


def test_expired_entry_returns_none(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(user_cache, "_monotonic", lambda: clock["t"])
    user_cache.put(1, "v", 30)
    clock["t"] = 1029.0
    assert user_cache.get(1) == "v"
    clock["t"] = 1031.0
    assert user_cache.get(1) is None


def test_invalidate_removes_entry():
    user_cache.put(1, "v", 60)
    user_cache.invalidate(1)
    assert user_cache.get(1) is None


def test_clear_empties_all():
    user_cache.put(1, "v", 60)
    user_cache.put(2, "v", 60)
    user_cache.clear()
    assert user_cache.get(1) is None
    assert user_cache.get(2) is None


def test_nonpositive_ttl_is_noop():
    user_cache.put(1, "v", 0)
    assert user_cache.get(1) is None
