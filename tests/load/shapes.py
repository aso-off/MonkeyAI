import os

from locust import LoadTestShape

# Пик и общая длительность задаются workflow'ом (выбор users/time)
_MAX_USERS = int(os.environ.get("LOAD_MAX_USERS", "500"))
_TOTAL = int(os.environ.get("LOAD_RUN_TIME_S", "270"))


def _spawn(users: int) -> int:
    return max(1, users // 10)


class StressShape(LoadTestShape):
    # ступенчатый рост до _MAX_USERS за _TOTAL: 20% -> 50% -> 100%
    def tick(self):
        t = self.get_run_time()
        if t >= _TOTAL:
            return None
        step = _TOTAL / 3
        if t < step:
            users = max(1, int(_MAX_USERS * 0.2))
        elif t < 2 * step:
            users = max(1, int(_MAX_USERS * 0.5))
        else:
            users = _MAX_USERS
        return users, _spawn(users)


class SpikeShape(LoadTestShape):
    # база <-> пик, 5 фаз по _TOTAL/5 (пики на фазах 2 и 4)
    def tick(self):
        t = self.get_run_time()
        if t >= _TOTAL:
            return None
        phase = _TOTAL / 5
        base = max(1, int(_MAX_USERS * 0.05))
        idx = int(t // phase)
        if idx in (1, 3):
            return _MAX_USERS, _MAX_USERS  # резкий набор в пик
        return base, _spawn(base)
