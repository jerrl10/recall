"""Structured logging to stderr.

stdout carries the MCP protocol, so every diagnostic must go to stderr — a
single stray byte on stdout corrupts the JSON-RPC stream and takes the session
down with no useful error.

Note content is never logged. A vault holds the user's own engineering notes,
and a log file is a much easier place to leak them from than the vault itself.
Identifiers, kinds, counts, and timings are enough to debug with.
"""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

LOGGER_NAME = "recall"

_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class _KeyValueFormatter(logging.Formatter):
    """Render records as ``level  event  key=value`` for greppability."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname:<7} {record.getMessage()}"
        fields = getattr(record, "fields", None)
        if fields:
            base += "  " + " ".join(f"{key}={_render(value)}" for key, value in fields.items())
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def _render(value: Any) -> str:
    text = str(value)
    return f'"{text}"' if " " in text else text


def configure(level: str = "INFO") -> None:
    """Attach a stderr handler to the Recall logger.

    Called once at startup. Safe to call again — handlers are replaced rather
    than accumulated, so repeated configuration cannot duplicate every line.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_KeyValueFormatter())
    logger.addHandler(handler)
    logger.setLevel(level.upper() if level.upper() in _LEVELS else "INFO")

    # Diagnostics must never travel up to a root handler that might target
    # stdout — that would corrupt the protocol stream.
    logger.propagate = False


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def event(level: int, message: str, **fields: Any) -> None:
    """Emit one structured record."""
    get_logger().log(level, message, extra={"fields": fields})


@contextmanager
def operation(name: str, **fields: Any) -> Iterator[dict[str, Any]]:
    """Time one tool call and record how it ended.

    Yields a dict the caller can add fields to as it learns them, so an
    outcome known only at the end still lands on the single summary line.
    """
    extra: dict[str, Any] = {}
    started = time.perf_counter()
    try:
        yield extra
    except Exception as exc:
        event(
            logging.ERROR,
            name,
            outcome="exception",
            error=type(exc).__name__,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            **fields,
            **extra,
        )
        raise
    else:
        event(
            logging.INFO,
            name,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            **fields,
            **extra,
        )
