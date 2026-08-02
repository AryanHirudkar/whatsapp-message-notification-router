"""General-purpose utility functions."""

from pathlib import Path
from typing import Any


def ensure_directory(path: Path) -> Path:
    """Ensure a directory exists and return its path.

    Args:
        path: Directory path to create if missing.

    Returns:
        The resolved directory path.
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_get(row: dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely retrieve a value from a dictionary row.

    Args:
        row: Source dictionary (e.g. CSV row).
        key: Key to look up.
        default: Value returned when the key is absent.

    Returns:
        The value for ``key`` or ``default``.
    """
    return row.get(key, default)


def join_evidence_ids(message_ids: list[str]) -> str:
    """Serialize evidence message IDs for CSV output.

    Args:
        message_ids: List of related message identifiers.

    Returns:
        Serialized evidence string for output CSV.
    """
    # TODO: Define canonical serialization format when output spec is finalized.
    return "|".join(message_ids)
