"""Structured logging setup with basic sensitive-value redaction."""

from __future__ import annotations

import logging
import re

SECRET_PATTERN = re.compile(r"(api[_-]?key|token|secret|password)=([^&\s]+)", re.IGNORECASE)


def redact_message(message: str) -> str:
    """Redact common key-value secret patterns from log messages."""

    return SECRET_PATTERN.sub(r"\1=<redacted>", message)


class RedactionFilter(logging.Filter):
    """Redact sensitive data before a record is emitted.

    Operates on the fully substituted message (msg % args), not on msg and
    args separately: a secret is frequently passed as a lazy %-style
    argument (`logger.info("api_key=%s", key)`) rather than baked into the
    template string, so it only appears next to its "key=" prefix once
    substitution has happened. Redacting beforehand and independently
    would also leave a %-placeholder in msg with no matching arg left,
    corrupting or crashing later formatting.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_message(record.getMessage())
        record.args = None
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging for local development.

    The redaction filter is attached to each handler, not the root logger:
    a filter on a logger only gates that logger's own calls, not records
    from named child loggers (the only kind get_logger() returns) that
    reach the handler by propagating up the hierarchy.
    """

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    redaction_filter = RedactionFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(redaction_filter)


def get_logger(name: str) -> logging.Logger:
    """Return a standard logger for application modules."""

    return logging.getLogger(name)
