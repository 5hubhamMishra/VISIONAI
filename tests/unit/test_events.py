from datetime import UTC, datetime, timedelta

import pytest
from pydantic import TypeAdapter, ValidationError

from visionai.core.events import (
    ActionRequest,
    ConfirmationRequest,
    GestureEvent,
    RiskLevel,
    SafeText,
    TranscriptEvent,
    contains_unsafe_characters,
    strip_unsafe_characters,
)


def test_transcript_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        TranscriptEvent(text="open\x00settings", confidence=0.5, language="en", is_final=True)


@pytest.mark.parametrize(
    "text",
    [
        "cats\u202ereversed",  # right-to-left override (Trojan Source / CVE-2021-42574)
        "hid\u200bden",  # zero width space
        "a\u200cb",  # zero width non-joiner
        "wrapped\u2066isolate\u2069",  # bidi isolate
        "line\u2028break",  # Unicode line separator
        "para\u2029graph",  # Unicode paragraph separator
        "\ufeffbom",  # byte-order mark / zero-width no-break space
        "word\u2060joiner",  # word joiner
    ],
)
def test_safe_text_rejects_unicode_bidi_and_invisible_characters(text: str) -> None:
    """A confirmation/proposal summary must display exactly what it appears
    to (Section 9) -- bidi-override and invisible characters can make
    displayed text misrepresent its real content, so `SafeText` (used by
    `LLMQuery`/`LLMReply`, `Intent`, `ActionRequest.arguments`,
    `ActionPlan.summary`, and both prompt types) must reject them the same
    way it already rejects ASCII control characters."""

    with pytest.raises(ValidationError):
        TypeAdapter(SafeText).validate_python(text)
    assert contains_unsafe_characters(text) is True


def test_safe_text_still_allows_tab_newline_and_carriage_return() -> None:
    """`ConversationMemory.build_query_text()` joins multi-turn context with
    real newlines; hardening against invisible/bidi characters must not
    also break that existing, intentional exemption."""

    text = "User: hi\tthere\nAssistant: hello\r\n"
    TypeAdapter(SafeText).validate_python(text)
    assert contains_unsafe_characters(text) is False


def test_contains_unsafe_characters_can_also_reject_line_breaks() -> None:
    """Single-line-only contexts (a URL, a search query, a suggested
    command phrase, a wake word) opt into rejecting tab/newline/CR too."""

    assert contains_unsafe_characters("a\nb", allow_line_breaks=False) is True
    assert contains_unsafe_characters("a\nb", allow_line_breaks=True) is False


def test_strip_unsafe_characters_removes_flagged_characters_only() -> None:
    stripped = strip_unsafe_characters("cats\u202ereversed\x00 but fine\ttext\n")

    assert stripped == "catsreversed but fine\ttext\n"
    assert contains_unsafe_characters(stripped) is False


def test_gesture_confidence_must_be_normalized() -> None:
    with pytest.raises(ValidationError):
        GestureEvent(gesture_id="pinch", hand="right", confidence=1.5, hold_ms=250)


def test_action_arguments_are_immutable() -> None:
    request = ActionRequest(
        capability_id="system.time",
        arguments={"format": "24h"},
        risk_level=RiskLevel.READ_ONLY,
    )

    with pytest.raises(TypeError):
        request.arguments["format"] = "12h"  # type: ignore[index]


def test_confirmation_must_expire_in_future() -> None:
    now = datetime.now(tz=UTC)
    request = ActionRequest(capability_id="system.time", risk_level=RiskLevel.SENSITIVE)

    with pytest.raises(ValidationError):
        ConfirmationRequest(
            request_id=request.id,
            action_summary="show time",
            risk_level=RiskLevel.SENSITIVE,
            expires_at=now - timedelta(seconds=1),
        )
