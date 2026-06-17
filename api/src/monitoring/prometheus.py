from __future__ import annotations

import re
import time
from collections.abc import Callable

from prometheus_client import Counter, Gauge, Histogram

api_client_requests_total = Counter(
    "api_client_requests_total",
    "API inbound requests total (clients: bot, future mini app, etc.).",
    labelnames=("method", "path", "status"),
)

# Aggregated by status class (2xx/3xx/4xx/5xx) for dashboards and health index.
api_client_http_status_class_total = Counter(
    "api_client_http_status_class_total",
    "API inbound requests by HTTP status class.",
    labelnames=("method", "path", "status_class"),
)

api_client_request_duration_seconds = Histogram(
    "api_client_request_duration_seconds",
    "API inbound request duration.",
    labelnames=("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)

api_requests_in_flight = Gauge(
    "api_requests_in_flight",
    "Number of in-flight HTTP requests.",
)

api_response_size_bytes = Histogram(
    "api_response_size_bytes",
    "HTTP response size in bytes.",
    labelnames=("method", "path"),
    buckets=(100, 500, 1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000),
)


_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def http_status_class(status_code: int) -> str:
    if 200 <= status_code < 300:
        return "2xx"
    if 300 <= status_code < 400:
        return "3xx"
    if 400 <= status_code < 500:
        return "4xx"
    if 500 <= status_code < 600:
        return "5xx"
    return "other"


def normalize_path(raw_path: str) -> str:
    # Keep label cardinality low: replace ids/uuids inside URLs.
    segments: list[str] = []
    for seg in raw_path.split("/"):
        if not seg:
            continue
        if seg.isdigit():
            segments.append(":id")
        elif _UUID_RE.match(seg):
            segments.append(":uuid")
        else:
            segments.append(seg)
    return "/" + "/".join(segments) if segments else "/"


def time_seconds() -> Callable[[], float]:
    return time.perf_counter
