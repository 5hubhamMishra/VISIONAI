from visionai.core.events import ActionRequest, RiskLevel
from visionai.platform.lock_state import StaticLockStateAdapter
from visionai.policy import ConfirmationService
from visionai.runtime import build_runtime


class _MutableLock:
    """A lock-state adapter whose value can change between calls.

    `StaticLockStateAdapter` is a frozen dataclass, so it cannot prove the
    runtime's `policy_context_factory` checks lock state fresh on every
    call rather than snapshotting it once at `build_runtime()` time.
    """

    def __init__(self) -> None:
        self.locked = False

    def is_locked(self) -> bool:
        return self.locked


def test_runtime_exposes_injected_confirmation_service() -> None:
    confirmation = ConfirmationService(ttl_seconds=5)

    runtime = build_runtime(confirmation=confirmation)

    assert runtime.confirmation is confirmation


def test_runtime_policy_context_factory_checks_lock_state_fresh_each_call() -> None:
    lock = _MutableLock()
    runtime = build_runtime(lock_state=lock)

    assert runtime.policy_context_factory().locked_screen is False
    lock.locked = True
    assert runtime.policy_context_factory().locked_screen is True


def test_runtime_denies_mutating_capability_while_screen_is_locked() -> None:
    runtime = build_runtime(lock_state=StaticLockStateAdapter(locked=True))
    request = ActionRequest(
        capability_id="app.open", arguments={"app": "notepad"}, risk_level=RiskLevel.REVERSIBLE
    )

    result = runtime.dispatcher.dispatch(request, runtime.policy_context_factory())

    assert result.success is False
    assert "locked" in result.message


def test_runtime_still_allows_read_only_capability_while_screen_is_locked() -> None:
    runtime = build_runtime(lock_state=StaticLockStateAdapter(locked=True))
    request = ActionRequest(capability_id="system.time", risk_level=RiskLevel.READ_ONLY)

    result = runtime.dispatcher.dispatch(request, runtime.policy_context_factory())

    assert result.success is True


def test_runtime_allows_mutating_capability_while_screen_is_unlocked() -> None:
    launched: list[str] = []
    runtime = build_runtime(
        lock_state=StaticLockStateAdapter(locked=False), launcher=launched.append
    )
    request = ActionRequest(
        capability_id="app.open", arguments={"app": "notepad"}, risk_level=RiskLevel.REVERSIBLE
    )

    result = runtime.dispatcher.dispatch(request, runtime.policy_context_factory())

    assert result.success is True
    assert launched == ["notepad.exe"]
