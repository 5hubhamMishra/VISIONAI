from visionai.policy import ConfirmationService
from visionai.runtime import build_runtime


def test_runtime_exposes_injected_confirmation_service() -> None:
    confirmation = ConfirmationService(ttl_seconds=5)

    runtime = build_runtime(confirmation=confirmation)

    assert runtime.confirmation is confirmation
