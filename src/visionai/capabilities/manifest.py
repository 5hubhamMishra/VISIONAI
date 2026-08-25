"""Strict capability manifest models.

Every executable operation must be declared here before policy can consider it.
Handlers are referenced by stable IDs, not arbitrary code strings.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from visionai.core.events import RiskLevel, SafeText, Slug


class ParameterType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"


class IdempotencyMode(StrEnum):
    IDEMPOTENT = "idempotent"
    IDEMPOTENCY_KEY = "idempotency_key"
    NON_IDEMPOTENT = "non_idempotent"


_DEFAULT_PLATFORMS: frozenset[Literal["windows"]] = frozenset({"windows"})


class ParameterSpec(BaseModel):
    """One allowed capability argument."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: ParameterType
    required: bool = False
    description: SafeText


class CapabilityManifest(BaseModel):
    """Policy-visible metadata for one executable capability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Slug
    description: SafeText
    parameters: dict[Slug, ParameterSpec] = Field(default_factory=dict)
    supported_platforms: frozenset[Literal["windows"]] = Field(
        default_factory=lambda: _DEFAULT_PLATFORMS
    )
    risk_level: RiskLevel
    permission_required: bool = False
    confirmation_required: bool = False
    rate_limit_per_minute: int = Field(gt=0, le=120)
    timeout_seconds: float = Field(gt=0, le=120)
    idempotency: IdempotencyMode
    audit_category: Slug
    handler_id: Slug
    undo_handler_id: Slug | None = None

    @model_validator(mode="after")
    def enforce_risk_controls(self) -> CapabilityManifest:
        if self.risk_level >= RiskLevel.SENSITIVE and not self.permission_required:
            raise ValueError("sensitive and destructive capabilities require permission")
        if self.risk_level >= RiskLevel.DESTRUCTIVE and not self.confirmation_required:
            raise ValueError("destructive capabilities require confirmation")
        return self
