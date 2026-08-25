from visionai.observability.logging import redact_message


def test_redacts_common_secret_values() -> None:
    message = "token=abc123 api_key=sk-test password=hunter2"

    assert redact_message(message) == "token=<redacted> api_key=<redacted> password=<redacted>"
