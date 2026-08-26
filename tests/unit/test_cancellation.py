import pytest

from visionai.core.cancellation import (
    CancellationToken,
    OperationCancelled,
    OperationController,
)


def test_cancellation_token_signals_and_raises() -> None:
    token = CancellationToken()

    assert token.is_cancelled is False
    token.cancel()

    assert token.is_cancelled is True
    with pytest.raises(OperationCancelled):
        token.raise_if_cancelled()


def test_operation_controller_cancels_active_token() -> None:
    controller = OperationController()
    token = controller.begin_operation()

    assert controller.has_active_operation is True
    assert controller.cancel_active_operation() is True

    assert token.is_cancelled is True


def test_operation_controller_reports_no_active_operation() -> None:
    controller = OperationController()

    assert controller.has_active_operation is False
    assert controller.cancel_active_operation() is False


def test_operation_controller_only_finishes_the_current_token() -> None:
    controller = OperationController()
    first = controller.begin_operation()
    second = controller.begin_operation()

    controller.finish_operation(first)

    assert controller.has_active_operation is True
    assert controller.cancel_active_operation() is True
    assert second.is_cancelled is True
