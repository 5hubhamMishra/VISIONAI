import pytest
from pydantic import ValidationError

from visionai.core.events import ActionRequest, ActionResult, GestureEvent, Intent, RiskLevel
from visionai.platform.lock_state import StaticLockStateAdapter
from visionai.policy import ConfirmationService
from visionai.policy.permissions import JsonPermissionStore
from visionai.recognition.gesture import TemporalGestureRecognizer
from visionai.runtime import build_runtime


async def _drain_available(bus):
    events = []
    while bus.size:
        events.append(await bus.next_event())
    return events


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


def test_runtime_exposes_injected_permission_store(tmp_path) -> None:
    permissions = JsonPermissionStore(tmp_path / "permissions.json")

    runtime = build_runtime(permission_store=permissions)

    assert runtime.permissions is permissions


def test_runtime_policy_context_factory_reflects_granted_permissions_fresh(tmp_path) -> None:
    """A grant made after build_runtime() is still picked up with no extra step.

    Mirrors the lock-state freshness test: `policy_context_factory` reads
    `permissions.granted_capabilities()` on every call rather than
    snapshotting it once, so `runtime.permissions.grant(...)` takes effect
    on the very next dispatch.
    """

    permissions = JsonPermissionStore(tmp_path / "permissions.json")
    runtime = build_runtime(permission_store=permissions)

    assert "clipboard.read" not in runtime.policy_context_factory().granted_capabilities

    permissions.grant("clipboard.read")

    assert "clipboard.read" in runtime.policy_context_factory().granted_capabilities


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


@pytest.mark.asyncio
async def test_runtime_input_adapter_transcript_reaches_the_real_orchestrator() -> None:
    launched: list[str] = []
    runtime = build_runtime(launcher=launched.append)

    event = await runtime.input_adapter.publish_transcript("open notepad", confidence=0.95)
    runtime.input_bus.close()
    await runtime.orchestrator.run_until_closed()
    outputs = await _drain_available(runtime.output_bus)

    assert event.text == "open notepad"
    assert launched == ["notepad.exe"]
    assert isinstance(outputs[0], Intent)
    assert isinstance(outputs[-1], ActionResult)


@pytest.mark.asyncio
async def test_runtime_input_adapter_voice_capture_uses_injected_transcriber() -> None:
    launched: list[str] = []
    runtime = build_runtime(launcher=launched.append)

    event = await runtime.input_adapter.publish_voice_capture(
        lambda: "open notepad", confidence=0.93
    )
    runtime.input_bus.close()
    await runtime.orchestrator.run_until_closed()

    assert event.text == "open notepad"
    assert event.is_final is True
    assert launched == ["notepad.exe"]


@pytest.mark.asyncio
async def test_runtime_input_adapter_publishes_validated_gesture_events() -> None:
    runtime = build_runtime()

    event = await runtime.input_adapter.publish_gesture(
        "pinch", hand="right", confidence=0.9, hold_ms=250
    )
    queued = await runtime.input_bus.next_event()

    assert isinstance(queued, GestureEvent)
    assert queued == event


@pytest.mark.asyncio
async def test_runtime_input_adapter_gesture_observation_requires_a_confirmed_vote() -> None:
    runtime = build_runtime()
    times = iter([0.0, 0.1, 0.45])
    recognizer = TemporalGestureRecognizer(min_hold_ms=400, clock=lambda: next(times))

    first = await runtime.input_adapter.publish_gesture_observation(
        recognizer, "pinch", hand="right", confidence=0.9
    )
    second = await runtime.input_adapter.publish_gesture_observation(
        recognizer, "pinch", hand="right", confidence=0.9
    )
    third = await runtime.input_adapter.publish_gesture_observation(
        recognizer, "pinch", hand="right", confidence=0.9
    )

    assert first is None
    assert second is None
    assert third is not None
    assert runtime.input_bus.size == 1
    queued = await runtime.input_bus.next_event()
    assert isinstance(queued, GestureEvent)
    assert queued == third


@pytest.mark.asyncio
async def test_runtime_input_adapter_rejects_invalid_transcript_without_publishing() -> None:
    runtime = build_runtime()

    with pytest.raises(ValidationError):
        await runtime.input_adapter.publish_transcript("open\x00notepad", confidence=0.95)

    assert runtime.input_bus.size == 0


@pytest.mark.asyncio
async def test_runtime_input_adapter_rejects_invalid_voice_capture_without_publishing() -> None:
    runtime = build_runtime()

    with pytest.raises(ValidationError):
        await runtime.input_adapter.publish_voice_capture(
            lambda: "open\x00notepad", confidence=0.95
        )

    assert runtime.input_bus.size == 0
