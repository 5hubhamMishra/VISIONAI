from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from visionai.core.errors import ConfirmationError
from visionai.core.events import ActionRequest, RiskLevel
from visionai.policy import ConfirmationService


def test_confirmation_is_bound_to_exact_request_and_single_use() -> None:
    service = ConfirmationService(ttl_seconds=30)
    request = ActionRequest(capability_id="clipboard.read", risk_level=RiskLevel.SENSITIVE)
    confirmation = service.create(request, action_summary="Read clipboard")

    service.validate(request, confirmation.id)

    with pytest.raises(ConfirmationError):
        service.validate(request, confirmation.id)


def test_confirmation_rejects_mismatched_request() -> None:
    service = ConfirmationService(ttl_seconds=30)
    request = ActionRequest(capability_id="clipboard.read", risk_level=RiskLevel.SENSITIVE)
    other = ActionRequest(capability_id="clipboard.read", risk_level=RiskLevel.SENSITIVE)
    confirmation = service.create(request, action_summary="Read clipboard")

    with pytest.raises(ConfirmationError):
        service.validate(other, confirmation.id)


def test_confirmation_rejects_expired_request() -> None:
    service = ConfirmationService(ttl_seconds=1)
    request = ActionRequest(capability_id="clipboard.read", risk_level=RiskLevel.SENSITIVE)
    confirmation = service.create(request, action_summary="Read clipboard")

    with pytest.raises(ConfirmationError):
        service.validate(
            request,
            confirmation.id,
            now=datetime.now(UTC) + timedelta(seconds=2),
        )

    with pytest.raises(ConfirmationError):
        service.validate(request, confirmation.id)


def test_confirmation_rejects_unknown_confirmation_id() -> None:
    service = ConfirmationService(ttl_seconds=30)
    request = ActionRequest(capability_id="clipboard.read", risk_level=RiskLevel.SENSITIVE)

    with pytest.raises(ConfirmationError):
        service.validate(request, uuid4())


def test_new_confirmation_replaces_old_pending_confirmation_for_same_request() -> None:
    service = ConfirmationService(ttl_seconds=30)
    request = ActionRequest(capability_id="clipboard.read", risk_level=RiskLevel.SENSITIVE)
    old_confirmation = service.create(request, action_summary="Read clipboard")
    new_confirmation = service.create(request, action_summary="Read clipboard")

    with pytest.raises(ConfirmationError):
        service.validate(request, old_confirmation.id)

    service.validate(request, new_confirmation.id)


def test_discard_removes_pending_confirmation_without_authorizing_it() -> None:
    service = ConfirmationService(ttl_seconds=30)
    request = ActionRequest(capability_id="clipboard.read", risk_level=RiskLevel.SENSITIVE)
    confirmation = service.create(request, action_summary="Read clipboard")

    assert service.discard(confirmation.id) is True
    assert service.discard(confirmation.id) is False
    with pytest.raises(ConfirmationError):
        service.validate(request, confirmation.id)
