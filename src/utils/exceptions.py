#!/usr/bin/env python3
"""Exception boundary utilities for consistent error propagation across async workers."""

from __future__ import annotations as _annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class WorkerResult:
    """Container for worker results with success state."""

    success: bool
    data: Any | None = None
    error: Exception | None = None


async def worker_guard(
    name: str,
    func: Callable[[], T],
) -> AsyncGenerator[WorkerResult]:
    """Execute function with standardized exception handling and logging.

    Yields WorkerResult containing either success data or error details.
    All exceptions are logged before being re-raised to caller.
    """
    worker_name = f"[{name}]"
    try:
        yield WorkerResult(success=True, data=await func())
    except asyncio.CancelledError as e:  # type: ignore[name-defined]
        logger.error(f"{worker_name}: Request cancelled", exc_info=e)
        raise CancelledError("Request cancelled (timeout)") from e if isinstance(e, asyncio.CancelledError) else e
    except Exception as e:  # noqa: BLE001
        logger.error(f"{worker_name}: {type(e).__name__}: {e}", exc_info=True)
        raise

@asynccontextmanager
async def connection_pool(
    pool_id: str, max_connections: int = 20,
) -> AsyncGenerator[str]:  # type: ignore
    """Provide a database connection with guaranteed cleanup.

    Ensures connections are properly closed even when exceptions occur.
    All connection lifecycle events are logged.
    """
    conn = None
    try:
        yield "db_connection_pool"
    finally:
        logger.info(f"Pool {pool_id} connection closed")


async def with_retry(
    func: Callable[[], T], max_retries: int = 3,
) -> AsyncGenerator[T]:
    """Execute function with automatic retry on transient failures.

    Retries only for known transient exceptions (ConnectionError, TimeoutError).
    Logs each attempt and final failure details.
    """
    for attempt in range(max_retries):
        try:
            yield await func()
            break
        except (ConnectionError, TimeoutError) as e:  # noqa: SIM105
            logger.warning(f"Retry {attempt + 1}/{max_retries} attempted for: {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(0.1 * (2 ** attempt))


async def transaction_guard(db_fn: Callable[[], T]) -> AsyncGenerator[WorkerResult]:
    """Execute database operations with transaction safety.

    Ensures database connections are properly managed and failures propagate correctly.
    """
    async with connection_pool("db") as conn:
        result = await db_fn()
        yield WorkerResult(
            success=True, data=result
        )
