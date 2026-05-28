from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

from prometheus_client import Counter, Histogram


tg_updates_total = Counter(
    "tg_updates_total",
    "Incoming Telegram updates received by webhook.",
    labelnames=("update_type",),
)

tg_webhook_requests_total = Counter(
    "tg_webhook_requests_total",
    "HTTP webhook requests received by bot.",
    labelnames=("status",),
)

tg_api_requests_total = Counter(
    "tg_api_requests_total",
    "Telegram Bot API requests total.",
    labelnames=("method", "ok"),
)

tg_api_request_duration_seconds = Histogram(
    "tg_api_request_duration_seconds",
    "Telegram Bot API request duration.",
    labelnames=("method",),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)


@contextmanager
def observe_duration_seconds(hist: Histogram, *label_values: str) -> Iterator[None]:
    t0 = time.perf_counter()
    try:
        yield
    finally:
        hist.labels(*label_values).observe(time.perf_counter() - t0)

