from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

import httpx
from openai import APIConnectionError, APIStatusError
from core.eval.telemetry import emit_telemetry

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    retries: int = 2
    base_delay: float = 0.1
    max_delay: float = 2.0

    def __post_init__(self) -> None:
        if self.retries < 0 or self.base_delay < 0 or self.max_delay < 0:
            raise ValueError("Retry parameters must be nonnegative.")


def error_category(exc: Exception) -> str:
    if isinstance(exc, APIStatusError):
        return "transient" if exc.status_code in {408, 429} or exc.status_code >= 500 else "permanent"
    if isinstance(exc, (TimeoutError, ConnectionError, httpx.TransportError, APIConnectionError)):
        return "transient"
    if isinstance(exc, (ValueError, TypeError, KeyError, AttributeError)):
        return "invalid_contract"
    return "unexpected"


async def with_retry(operation: Callable[[], Awaitable[T]], *, component: str,
                     policy: RetryPolicy = RetryPolicy()) -> T:
    for attempt in range(policy.retries + 1):
        try:
            return await operation()
        except Exception as exc:  # extension boundary: classify, record, then retry or propagate
            category = error_category(exc)
            retrying = category == "transient" and attempt < policy.retries
            emit_telemetry("execution_error", component=component,
                           error_type=type(exc).__name__, category=category,
                           attempt=attempt + 1, retrying=retrying)
            if not retrying:
                raise
            await asyncio.sleep(min(policy.max_delay, policy.base_delay * 2 ** attempt))
    raise AssertionError("unreachable")
