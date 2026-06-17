"""New Relic helper utilities for aiogram bot handlers.

Provides safe wrappers that gracefully degrade if the ``newrelic`` package
is not installed (e.g. in local development without the agent).

Usage in aiogram handlers::

    from src.monitoring.newrelic_helpers import nr_transaction_name, nr_add_custom_parameter

    async def cmd_start(message: Message):
        nr_transaction_name("command/start")
        nr_add_custom_parameter("user_id", message.from_user.id)
        ...
"""
from __future__ import annotations

import functools
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

try:
    import newrelic.agent as _nr  # type: ignore[import-not-found] # pyright: ignore[reportMissingImports]
except ImportError:
    _nr = None


def nr_transaction_name(name: str) -> None:
    """Set a custom New Relic transaction name for the current handler.

    Since all Telegram updates arrive on the single ``POST /webhook`` endpoint,
    every handler would otherwise be grouped under one transaction.
    Call this at the top of each handler to get per-command / per-callback
    breakdowns in New Relic APM.

    Examples::

        nr_transaction_name("command/start")
        nr_transaction_name("callback/select_model")
        nr_transaction_name("message/text")
        nr_transaction_name("message/voice")
    """
    if _nr is not None:
        _nr.set_transaction_name(name, group="Aiogram")


def nr_notice_error() -> None:
    """Report the current exception to New Relic."""
    if _nr is not None:
        _nr.notice_error()


def nr_add_custom_parameter(key: str, value) -> None:
    """Add a custom parameter to the current transaction.

    Useful for filtering/searching transactions in New Relic by user_id,
    chat_mode, model, etc.
    """
    if _nr is not None:
        _nr.add_custom_attribute(key, value)


def nr_add_custom_parameters(params: dict) -> None:
    """Add multiple custom parameters to the current transaction."""
    if _nr is not None:
        # Convert dictionary to list of tuples for add_custom_attributes
        attrs = [(k, v) for k, v in params.items()]
        _nr.add_custom_attributes(attrs)


def nr_record_custom_event(event_type: str, params: dict | None = None) -> None:
    """Record a custom event in New Relic Insights.

    Useful for business metrics::

        nr_record_custom_event("ChatCompletion", {
            "user_id": 123,
            "model": "gpt-4o",
            "tokens": 500,
        })
    """
    if _nr is not None:
        app = _nr.application()
        if app:
            _nr.record_custom_event(event_type, params or {}, application=app)


def nr_background_task(name: str):
    """Decorator to wrap an async function as a New Relic background task.

    Use for periodic tasks, heartbeats, system_info loops, etc.::

        @nr_background_task("heartbeat")
        async def _heartbeat(redis):
            ...
    """

    def decorator(func: Callable) -> Callable:
        if _nr is None:
            return func
        nr = _nr

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            with nr.BackgroundTask(
                application=nr.application(),
                name=name,
                group="Task",
            ):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
