"""Timing utilities for performance measurement."""

import time
from collections.abc import Generator
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, TypeVar

from code.utils.logger import get_logger

F = TypeVar("F", bound=Callable[..., Any])

_logger = get_logger("timer")


@contextmanager
def timer(label: str) -> Generator[None, None, None]:
    """Context manager that logs elapsed time for a block of code.

    Args:
        label: Human-readable label for the timed operation.

    Yields:
        Control to the wrapped block.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        _logger.debug("%s completed in %.4fs", label, elapsed)


def timed(label: str | None = None) -> Callable[[F], F]:
    """Decorator that logs elapsed time for a function call.

    Args:
        label: Optional override for the log label. Defaults to function name.

    Returns:
        Decorator wrapping the target function.
    """

    def decorator(func: F) -> F:
        operation = label or func.__name__

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with timer(operation):
                return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
