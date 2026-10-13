"""Shared UTC clock for timestamps recorded in downloadable results."""

from datetime import UTC, datetime


def now() -> datetime:
    """Return the current UTC instant."""
    return datetime.now(UTC)
