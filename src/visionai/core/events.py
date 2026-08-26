"""Typed, validated contracts exchanged between subsystems.

These models are the only shapes that may cross a subsystem boundary
(recognition -> orchestrator -> policy -> dispatcher -> UI/audit). Nothing
downstream should accept a raw dict, and nothing derived from LLM or model
output should be trusted until it has passed validation here: unknown
fields are rejected, strings are length- and character-bounded, and enums
are closed sets.
"""

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import IntEnum
from types import MappingProxyType
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# A short human/spoken-language string: no control characters, bounded length.
SafeText = Annotated[
    str,
    StringConstraints(max_length=2000, pattern=r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f]*$"),
]

# A stable identifier used for capability IDs, intent names, gesture IDs.
Slug = Annotated[str, StringConstraints(max_length=100, pattern=r"^[a-z][a-z0-9_.-]*$")]


class RiskLevel(IntEnum):
    """Capability risk tiers. See docs/SECURITY.md for the full policy."""

    READ_ONLY = 0
    REVERSIBLE = 1
    SENSITIVE = 2
    DESTRUCTIVE = 3
    PROHIBITED = 4


class EventBase(BaseModel):
    """Common fields for every typed event: identity, timing, and audit trail."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InputEvent(EventBase):
    """A raw user input signal before any recognition has occurred."""

    source: Literal["voice", "gesture", "keyboard", "pointer"]


class AudioEvent(EventBase):
    """Metadata for a captured audio segment. Raw PCM is never embedded here."""

    sample_rate_hz: int = Field(gt=0, le=192_000)
    channels: int = Field(gt=0, le=8)
    duration_seconds: float = Field(gt=0, le=120)


class TranscriptEvent(EventBase):
    """A speech-to-text result, partial or final."""

    text: SafeText
    confidence: float = Field(ge=0.0, le=1.0)
    language: str = Field(max_length=10)
    is_final: bool


class GestureEvent(EventBase):
    """A policy-approved gesture, already passed through temporal voting."""

    gesture_id: Slug
    hand: Literal["left", "right"]
    confidence: float = Field(ge=0.0, le=1.0)
    hold_ms: int = Field(ge=0)


class Intent(EventBase):
    """A parsed, structured interpretation of user input."""

    name: Slug
    confidence: float = Field(ge=0.0, le=1.0)
    slots: Mapping[str, SafeText] = Field(default_factory=dict)
    source_text: SafeText

    @field_validator("slots")
    @classmethod
    def freeze_slots(cls, value: Mapping[str, SafeText]) -> Mapping[str, SafeText]:
        return MappingProxyType(dict(value))


class ActionRequest(EventBase):
    """A single request to invoke one registered capability."""

    capability_id: Slug
    arguments: Mapping[str, SafeText | int | float | bool] = Field(default_factory=dict)
    risk_level: RiskLevel

    @field_validator("arguments")
    @classmethod
    def freeze_arguments(
        cls, value: Mapping[str, SafeText | int | float | bool]
    ) -> Mapping[str, SafeText | int | float | bool]:
        return MappingProxyType(dict(value))


class ActionPlan(EventBase):
    """An ordered sequence of action requests proposed for one user turn."""

    steps: tuple[ActionRequest, ...]
    summary: SafeText


class ActionResult(EventBase):
    """The outcome of executing one `ActionRequest`."""

    request_id: UUID
    success: bool
    message: SafeText
    undo_token: str | None = None


class ConfirmationRequest(EventBase):
    """A pending confirmation for a sensitive or destructive action."""

    request_id: UUID
    action_summary: SafeText
    risk_level: RiskLevel
    expires_at: datetime

    @model_validator(mode="after")
    def expires_after_creation(self) -> "ConfirmationRequest":
        if self.expires_at <= self.created_at:
            raise ValueError("confirmation must expire after creation")
        return self


class PermissionRequest(EventBase):
    """A pending request to grant a capability permission."""

    request_id: UUID
    capability_id: Slug
    action_summary: SafeText
    risk_level: RiskLevel


class PermissionDecision(EventBase):
    """A recorded grant or denial of a capability for the current user."""

    capability_id: Slug
    granted: bool
    decided_by: Literal["user", "policy_default"]


class AuditEvent(EventBase):
    """An entry in the audit history. Never includes raw sensitive content."""

    category: SafeText
    actor: Literal["user", "system", "llm"]
    summary: SafeText
    risk_level: RiskLevel | None = None


class ErrorEvent(EventBase):
    """A domain error surfaced to the UI or audit log."""

    error_type: SafeText
    message: SafeText
    recoverable: bool
