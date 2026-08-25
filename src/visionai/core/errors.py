"""Domain error hierarchy.

Boundary code (I/O, adapters, providers) should catch specific exceptions and
re-raise as one of these so callers can handle failures by category instead
of relying on broad `except Exception` blocks.
"""


class VisionAIError(Exception):
    """Base class for all domain errors raised within VisionAI."""


class ValidationError(VisionAIError):
    """Input, event, or contract failed schema or invariant validation."""


class PolicyError(VisionAIError):
    """A requested action was denied by the policy or permission engine."""


class CapabilityError(VisionAIError):
    """A registered capability failed during execution."""


class UnregisteredCapabilityError(CapabilityError):
    """An action referenced a capability ID that is not registered."""


class ConfirmationError(VisionAIError):
    """A confirmation was missing, expired, mismatched, or replayed."""


class DeviceError(VisionAIError):
    """A hardware device (microphone, camera, speaker) is unavailable."""


class ProviderError(VisionAIError):
    """An external provider (LLM, STT, TTS) failed or timed out."""


class StateTransitionError(VisionAIError):
    """An invalid or disallowed state transition was attempted."""


class EventBusClosed(VisionAIError):
    """An event was requested from, or published to, a closed event bus."""


class RateLimitError(PolicyError):
    """A capability exceeded its configured rate limit."""


class DispatchError(CapabilityError):
    """A capability request could not be dispatched safely."""


class UrlValidationError(ValidationError):
    """A URL or browser search query failed safety validation."""


class StorageError(VisionAIError):
    """A local persistence operation failed."""


class PlatformStateError(VisionAIError):
    """Platform state could not be checked safely."""
