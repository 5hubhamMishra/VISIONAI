"""Deterministic policy checks for action requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from visionai.capabilities.manifest import CapabilityManifest, ParameterType
from visionai.capabilities.registry import CapabilityRegistry
from visionai.core.events import ActionRequest, RiskLevel
from visionai.platform.lock_state import LockStateAdapter
from visionai.policy.permissions import JsonPermissionStore
from visionai.policy.rate_limit import FixedWindowRateLimiter


@dataclass(frozen=True, slots=True)
class PolicyContext:
    """Runtime facts needed for policy evaluation."""

    platform: str = "windows"
    granted_capabilities: frozenset[str] = field(default_factory=frozenset)
    confirmed_request_ids: frozenset[UUID] = field(default_factory=frozenset)
    locked_screen: bool = False

    @classmethod
    def from_sources(
        cls,
        *,
        permission_store: JsonPermissionStore,
        lock_state: LockStateAdapter,
        platform: str = "windows",
        confirmed_request_ids: frozenset[UUID] = frozenset(),
    ) -> PolicyContext:
        """Build policy context from trusted local adapters."""

        return cls(
            platform=platform,
            granted_capabilities=permission_store.granted_capabilities(),
            confirmed_request_ids=confirmed_request_ids,
            locked_screen=lock_state.is_locked(),
        )


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Result of evaluating one request."""

    allowed: bool
    reason: str
    requires_confirmation: bool = False


class PolicyEngine:
    """Applies registration, platform, permission, confirmation, and schema checks."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        rate_limiter: FixedWindowRateLimiter | None = None,
    ) -> None:
        self._registry = registry
        self._rate_limiter = rate_limiter

    def evaluate(
        self,
        request: ActionRequest,
        context: PolicyContext,
        *,
        consume_rate_limit: bool = True,
    ) -> PolicyDecision:
        manifest = self._registry.get(request.capability_id)
        argument_error = _first_argument_error(request, manifest)
        if argument_error:
            return PolicyDecision(False, argument_error)
        if context.platform not in manifest.supported_platforms:
            return PolicyDecision(False, "capability is not supported on this platform")
        if manifest.risk_level == RiskLevel.PROHIBITED:
            return PolicyDecision(False, "prohibited capability")
        if context.locked_screen and manifest.risk_level > RiskLevel.READ_ONLY:
            return PolicyDecision(False, "mutating actions are blocked while the screen is locked")
        if manifest.permission_required and manifest.id not in context.granted_capabilities:
            return PolicyDecision(False, "permission has not been granted")
        needs_confirmation = (
            manifest.confirmation_required or manifest.risk_level >= RiskLevel.SENSITIVE
        )
        if needs_confirmation and request.id not in context.confirmed_request_ids:
            return PolicyDecision(
                False,
                "fresh confirmation is required",
                requires_confirmation=True,
            )
        if self._rate_limiter:
            rate_allowed = (
                self._rate_limiter.allow(manifest.id, manifest.rate_limit_per_minute)
                if consume_rate_limit
                else self._rate_limiter.would_allow(
                    manifest.id, manifest.rate_limit_per_minute
                )
            )
            if not rate_allowed:
                return PolicyDecision(False, "rate limit exceeded")
        return PolicyDecision(True, "allowed")


def _first_argument_error(request: ActionRequest, manifest: CapabilityManifest) -> str | None:
    allowed_names = set(manifest.parameters)
    provided_names = set(request.arguments)
    unknown = provided_names - allowed_names
    if unknown:
        return f"unknown argument: {sorted(unknown)[0]}"

    for name, spec in manifest.parameters.items():
        if spec.required and name not in request.arguments:
            return f"missing required argument: {name}"
        if name not in request.arguments:
            continue
        value = request.arguments[name]
        if spec.type is ParameterType.STRING and not isinstance(value, str):
            return f"argument has wrong type: {name}"
        if spec.type is ParameterType.INTEGER and (
            not isinstance(value, int) or isinstance(value, bool)
        ):
            return f"argument has wrong type: {name}"
        if spec.type is ParameterType.NUMBER and (
            not isinstance(value, int | float) or isinstance(value, bool)
        ):
            return f"argument has wrong type: {name}"
        if spec.type is ParameterType.BOOLEAN and not isinstance(value, bool):
            return f"argument has wrong type: {name}"
    return None
