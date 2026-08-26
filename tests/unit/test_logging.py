import logging

from visionai.observability.logging import RedactionFilter, configure_logging, redact_message


def test_redacts_common_secret_values() -> None:
    message = "token=abc123 api_key=sk-test password=hunter2"

    assert redact_message(message) == "token=<redacted> api_key=<redacted> password=<redacted>"


def _make_record(msg: str, args: object) -> logging.LogRecord:
    return logging.LogRecord(
        name="visionai.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )


def test_redaction_filter_redacts_lazy_percent_style_arguments() -> None:
    """Regression: a secret passed as a %-style logging argument -- the
    idiomatic way to log, e.g. logger.info("api_key=%s", key) -- must
    still be redacted even though it has no "key=" prefix of its own
    until after substitution.
    """
    record = _make_record("user authenticated with api_key=%s", ("sk-supersecret123",))

    assert RedactionFilter().filter(record) is True
    assert record.getMessage() == "user authenticated with api_key=<redacted>"


def test_redaction_filter_handles_dict_style_arguments() -> None:
    record = _make_record(
        "login for %(user)s with token=%(token)s", {"user": "alice", "token": "zt-9988"}
    )

    assert RedactionFilter().filter(record) is True
    assert record.getMessage() == "login for alice with token=<redacted>"


def test_redaction_filter_does_not_corrupt_messages_with_no_secret() -> None:
    record = _make_record("processed %d events in %s", (3, "0.2s"))

    assert RedactionFilter().filter(record) is True
    assert record.getMessage() == "processed 3 events in 0.2s"


def test_configure_logging_attaches_redaction_filter_to_every_handler() -> None:
    """Regression: the filter must be attached to handlers, not the root
    logger. A filter attached via Logger.addFilter only gates that
    logger's own calls -- it is never consulted for records from named
    child loggers (the only kind get_logger() returns) that reach the
    same handlers purely by propagating up the hierarchy.
    """
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        root.handlers = []
        configure_logging("INFO")

        assert root.handlers, "configure_logging should install at least one handler"
        for handler in root.handlers:
            assert any(isinstance(f, RedactionFilter) for f in handler.filters)
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)
