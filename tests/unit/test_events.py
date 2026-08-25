from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from visionai.core.events import (
    ActionRequest,
    ConfirmationRequest,
    GestureEvent,
    RiskLevel,
    TranscriptEvent,
)


def test_transcript_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        TranscriptEvent(text="open\x00settings", confidence=0.5, language="en", is_final=True)


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
