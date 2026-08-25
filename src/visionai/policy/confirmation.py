"""Fresh, bound confirmation handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from visionai.core.errors import ConfirmationError
from visionai.core.events import ActionRequest, ConfirmationRequest, RiskLevel


class ConfirmationService:
    """Creates and validates short-lived confirmations for exact requests."""

    def __init__(self, ttl_seconds: int = 30) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        self._ttl_seconds = ttl_seconds
        self._pending: dict[UUID, ConfirmationRequest] = {}

    def create(self, request: ActionRequest, *, action_summary: str) -> ConfirmationRequest:
        if request.risk_level < RiskLevel.SENSITIVE:
            raise ConfirmationError("confirmation is only required for sensitive actions")
        stale_ids = [
            pending_id
            for pending_id, pending in self._pending.items()
            if pending.request_id == request.id
        ]
        for pending_id in stale_ids:
            del self._pending[pending_id]
        confirmation = ConfirmationRequest(
            id=uuid4(),
            request_id=request.id,
            action_summary=action_summary,
            risk_level=request.risk_level,
            expires_at=datetime.now(UTC) + timedelta(seconds=self._ttl_seconds),
        )
        self._pending[confirmation.id] = confirmation
        return confirmation

    def validate(
        self,
        request: ActionRequest,
        confirmation_id: UUID,
        *,
        now: datetime | None = None,
    ) -> None:
        confirmation = self._pending.get(confirmation_id)
        if confirmation is None:
            raise ConfirmationError("confirmation is missing or already used")
        if confirmation.request_id != request.id:
            raise ConfirmationError("confirmation is not bound to this request")
        if (now or datetime.now(UTC)) >= confirmation.expires_at:
            self._pending.pop(confirmation_id, None)
            raise ConfirmationError("confirmation has expired")
        self._pending.pop(confirmation_id, None)
