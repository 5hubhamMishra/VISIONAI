"""Structured logging setup with basic sensitive-value redaction."""

from __future__ import annotations

import logging
import re
from collections.abc import MutableMapping

SECRET_PATTERN = re.compile(r"(api[_-]?key|token|secret|password)=([^&\s]+)", re.IGNORECASE)


def redact_message(message: str) -> str:
    """Redact common key-value secret patterns from log messages."""

    return SECRET_PATTERN.sub(r"\1=<redacted>", message)


class RedactionFilter(logging.Filter):
    """Redact sensitive data before a record is emitted."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_message(str(record.msg))
        if isinstance(record.args, MutableMapping):
            record.args = {key: redact_message(str(value)) for key, value in record.args.items()}
        elif isinstance(record.args, tuple):
            record.args = tuple(redact_message(str(value)) for value in record.args)
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging for local development."""

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger().addFilter(RedactionFilter())


def get_logger(name: str) -> logging.Logger:
    """Return a standard logger for application modules."""

    return logging.getLogger(name)
