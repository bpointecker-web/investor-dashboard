"""Strukturiertes Logging via structlog.

In Prod (``LOG_JSON=true``) werden JSON-Logs ausgegeben, in Dev gut lesbare
key=value-Zeilen. Einmalig beim App-Start konfiguriert.
"""

from __future__ import annotations

import logging
import sys

import structlog

# Mutierbarer Container statt `global` -> idempotente Konfiguration ohne PLW0603.
_state: dict[str, bool] = {"configured": False}


def configure_logging(*, level: str = "INFO", json_logs: bool = False) -> None:
    """Konfiguriert structlog + stdlib-Logging idempotent."""
    if _state["configured"]:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _state["configured"] = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Liefert einen gebundenen structlog-Logger."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
