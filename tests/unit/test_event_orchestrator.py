from uuid import uuid4

import pytest

from visionai.capabilities import CapabilityManifest, CapabilityRegistry, IdempotencyMode
from visionai.capabilities.dispatcher import SerializedDispatcher
from visionai.core.cancellation import OperationController
from visionai.core.event_bus import EventBus
from visionai.core.events import (
    ActionPlan,
    ActionRequest,
    ActionResult,
    ConfirmationRequest,
    ErrorEvent,
    Intent,
    RiskLevel,
    TranscriptEvent,
)
from visionai.core.state import AppState, StateMachine
from visionai.observability import InMemoryAuditSink
from visionai.orchestration.event_orchestrator import EventOrchestrator
from visionai.policy import ConfirmationService, FixedWindowRateLimiter, PolicyContext, PolicyEngine
from visionai.runtime import build_runtime


async def _drain_available(bus: EventBus):
    events = []
    while bus.size:
        events.append(await bus.next_event())
    return events


def _sensitive_manifest() -> CapabilityManifest:
    return CapabilityManifest(
        id="test.sensitive",
        description="A synthetic sensitive capability for confirmation-gate tests.",
        risk_level=RiskLevel.SENSITIVE,
        permission_required=True,
        confirmation_required=True,
        rate_limit_per_minute=10,
        timeout_seconds=3,
        idempotency=IdempotencyMode.IDEMPOTENT,
        audit_category="test.sensitive",
        handler_id="test.sensitive",
    )


class _FixedPlanner:
    """Always proposes one step for the synthetic sensitive capability.

    A real `TextCommandPlanner` only knows the built-in registered
    capabilities, so it cannot produce a plan for a test-only manifest --
    this stands in for it, matching the injected-fake pattern used
    elsewhere in this codebase (launcher, browser opener, key presser).
    """

    def __init__(self, *, summary: str) -> None:
        self._summary = summary

    def plan(self, text: str) -> tuple[Intent, ActionPlan]:
        # A fresh ActionRequest per call, so two calls never collide via
        # ConfirmationService's own same-request_id stale-cleanup.
        request = ActionRequest(capability_id="test.sensitive", risk_level=RiskLevel.SENSITIVE)
        intent = Intent(name="test.sensitive", confidence=1.0, source_text=text)
        return intent, ActionPlan(steps=(request,), summary=self._summary)


def _build_sensitive_orchestrator() -> tuple[EventOrchestrator, EventBus, list[ActionRequest]]:
    registry = CapabilityRegistry([_sensitive_manifest()])
    calls: list[ActionRequest] = []

    def handler(request: ActionRequest) -> ActionResult:
        calls.append(request)
        return ActionResult(request_id=request.id, success=True, message="done")

    dispatcher = SerializedDispatcher(
        registry=registry,
        policy=PolicyEngine(registry, FixedWindowRateLimiter()),
        audit=InMemoryAuditSink(),
        handlers={"test.sensitive": handler},
    )
    output_bus = EventBus(max_size=10)
    orchestrator = EventOrchestrator(
        input_bus=EventBus(max_size=10),
        output_bus=output_bus,
        planner=_FixedPlanner(summary="Do the sensitive thing."),
        dispatcher=dispatcher,
        operations=OperationController(),
        confirmation=ConfirmationService(),
        policy_context_factory=lambda: PolicyContext(
            granted_capabilities=frozenset({"test.sensitive"})
        ),
    )
    return orchestrator, output_bus, calls


@pytest.mark.asyncio
async def test_orchestrator_requests_confirmation_for_a_sensitive_capability() -> None:
    orchestrator, output_bus, calls = _build_sensitive_orchestrator()
    event = TranscriptEvent(
        text="do the sensitive thing", confidence=1.0, language="en", is_final=True
    )

    await orchestrator.process_event(event)
    outputs = await _drain_available(output_bus)

    assert [type(output) for output in outputs] == [Intent, ActionPlan, ConfirmationRequest]
    confirmation = outputs[2]
    assert confirmation.action_summary == "Do the sensitive thing."
    assert orchestrator.state_machine.state is AppState.AWAITING_CONFIRMATION
    assert calls == []


@pytest.mark.asyncio
async def test_orchestrator_confirm_executes_the_pending_request() -> None:
    orchestrator, output_bus, calls = _build_sensitive_orchestrator()
    event = TranscriptEvent(
        text="do the sensitive thing", confidence=1.0, language="en", is_final=True
    )
    await orchestrator.process_event(event)
    confirmation = (await _drain_available(output_bus))[2]

    await orchestrator.confirm(confirmation.id)
    outputs = await _drain_available(output_bus)

    assert len(calls) == 1
    assert isinstance(outputs[0], ActionResult)
    assert outputs[0].success is True
    assert orchestrator.state_machine.state is AppState.IDLE


@pytest.mark.asyncio
async def test_orchestrator_confirm_rejects_unknown_id() -> None:
    orchestrator, output_bus, calls = _build_sensitive_orchestrator()

    await orchestrator.confirm(uuid4())
    outputs = await _drain_available(output_bus)

    assert calls == []
    assert len(outputs) == 1
    assert isinstance(outputs[0], ErrorEvent)
    assert "missing or already used" in outputs[0].message


@pytest.mark.asyncio
async def test_orchestrator_confirm_is_not_replayable() -> None:
    orchestrator, output_bus, calls = _build_sensitive_orchestrator()
    event = TranscriptEvent(
        text="do the sensitive thing", confidence=1.0, language="en", is_final=True
    )
    await orchestrator.process_event(event)
    confirmation = (await _drain_available(output_bus))[2]

    await orchestrator.confirm(confirmation.id)
    await _drain_available(output_bus)
    await orchestrator.confirm(confirmation.id)
    replay_outputs = await _drain_available(output_bus)

    assert len(calls) == 1
    assert isinstance(replay_outputs[0], ErrorEvent)


@pytest.mark.asyncio
async def test_orchestrator_cancel_pending_confirmation_prevents_execution() -> None:
    orchestrator, output_bus, calls = _build_sensitive_orchestrator()
    event = TranscriptEvent(
        text="do the sensitive thing", confidence=1.0, language="en", is_final=True
    )
    await orchestrator.process_event(event)
    confirmation = (await _drain_available(output_bus))[2]

    removed = orchestrator.cancel_pending_confirmation(confirmation.id)
    await orchestrator.confirm(confirmation.id)
    replay_outputs = await _drain_available(output_bus)

    assert removed is True
    assert calls == []
    assert isinstance(replay_outputs[0], ErrorEvent)
    assert orchestrator.state_machine.state is AppState.IDLE


def test_orchestrator_cancel_pending_confirmation_is_a_noop_for_unknown_id() -> None:
    orchestrator, _output_bus, _calls = _build_sensitive_orchestrator()

    assert orchestrator.cancel_pending_confirmation(uuid4()) is False


@pytest.mark.asyncio
async def test_orchestrator_surfaces_a_risk_level_mismatch_as_an_error_not_a_crash() -> None:
    """A request whose self-reported risk_level disagrees with the manifest's.

    Policy's `requires_confirmation` is driven by the trusted manifest risk
    level, but `ConfirmationService.create()` separately checks the
    request's own (caller-supplied) `risk_level` field and refuses to
    create a confirmation below SENSITIVE. A real planner never produces
    this mismatch (it always copies risk_level from the same manifest
    lookup policy uses), but a buggy or malicious planner/direct caller
    could -- this should degrade to an ErrorEvent, never a crash or a
    silently-executed action.
    """

    class _MismatchedPlanner:
        def plan(self, text: str) -> tuple[Intent, ActionPlan]:
            request = ActionRequest(capability_id="test.sensitive", risk_level=RiskLevel.READ_ONLY)
            intent = Intent(name="test.sensitive", confidence=1.0, source_text=text)
            return intent, ActionPlan(steps=(request,), summary="Do the sensitive thing.")

    registry = CapabilityRegistry([_sensitive_manifest()])
    calls: list[ActionRequest] = []

    def handler(request: ActionRequest) -> ActionResult:
        calls.append(request)
        return ActionResult(request_id=request.id, success=True, message="done")

    dispatcher = SerializedDispatcher(
        registry=registry,
        policy=PolicyEngine(registry, FixedWindowRateLimiter()),
        audit=InMemoryAuditSink(),
        handlers={"test.sensitive": handler},
    )
    output_bus = EventBus(max_size=10)
    orchestrator = EventOrchestrator(
        input_bus=EventBus(max_size=10),
        output_bus=output_bus,
        planner=_MismatchedPlanner(),
        dispatcher=dispatcher,
        operations=OperationController(),
        confirmation=ConfirmationService(),
        policy_context_factory=lambda: PolicyContext(
            granted_capabilities=frozenset({"test.sensitive"})
        ),
    )
    event = TranscriptEvent(
        text="do the sensitive thing", confidence=1.0, language="en", is_final=True
    )

    await orchestrator.process_event(event)
    outputs = await _drain_available(output_bus)

    assert calls == []
    assert isinstance(outputs[-1], ErrorEvent)
    assert orchestrator.state_machine.state is AppState.IDLE


@pytest.mark.asyncio
async def test_orchestrator_new_command_supersedes_a_pending_confirmation() -> None:
    orchestrator, output_bus, calls = _build_sensitive_orchestrator()
    event = TranscriptEvent(
        text="do the sensitive thing", confidence=1.0, language="en", is_final=True
    )

    await orchestrator.process_event(event)
    first_outputs = await _drain_available(output_bus)
    first_confirmation = first_outputs[-1]
    assert orchestrator.state_machine.state is AppState.AWAITING_CONFIRMATION

    await orchestrator.process_event(event)
    outputs = await _drain_available(output_bus)
    await orchestrator.confirm(first_confirmation.id)
    stale_outputs = await _drain_available(output_bus)

    # The first pending confirmation is abandoned, never executed -- the
    # second command produces its own fresh confirmation prompt instead.
    assert calls == []
    assert isinstance(outputs[-1], ConfirmationRequest)
    assert isinstance(stale_outputs[-1], ErrorEvent)
    assert "missing or already used" in stale_outputs[-1].message
    assert orchestrator.state_machine.state is AppState.AWAITING_CONFIRMATION


@pytest.mark.asyncio
async def test_orchestrator_ignores_partial_transcripts() -> None:
    runtime = build_runtime()
    event = TranscriptEvent(text="open notepad", confidence=0.8, language="en", is_final=False)

    await runtime.orchestrator.process_event(event)

    assert runtime.output_bus.size == 0
    assert runtime.state_machine.state is AppState.IDLE


@pytest.mark.asyncio
async def test_orchestrator_plans_and_dispatches_final_transcript() -> None:
    launched: list[str] = []
    runtime = build_runtime(launcher=launched.append)
    event = TranscriptEvent(text="open notepad", confidence=0.95, language="en", is_final=True)

    await runtime.orchestrator.process_event(event)
    outputs = await _drain_available(runtime.output_bus)

    assert [type(output) for output in outputs] == [Intent, ActionPlan, ActionResult]
    assert outputs[0].name == "app.open"
    assert outputs[1].steps[0].capability_id == "app.open"
    assert outputs[2].success is True
    assert launched == ["notepad.exe"]
    assert runtime.state_machine.state is AppState.IDLE
    assert runtime.operations.has_active_operation is False


@pytest.mark.asyncio
async def test_orchestrator_publishes_non_executable_plan_for_unknown_text() -> None:
    runtime = build_runtime()
    event = TranscriptEvent(text="do something vague", confidence=0.5, language="en", is_final=True)

    await runtime.orchestrator.process_event(event)
    outputs = await _drain_available(runtime.output_bus)

    assert [type(output) for output in outputs] == [Intent, ActionPlan]
    assert outputs[0].name == "conversation.reply"
    assert outputs[1].steps == ()
    assert runtime.audit.list() == ()
    assert runtime.state_machine.state is AppState.IDLE


@pytest.mark.asyncio
async def test_orchestrator_dispatches_stop_without_starting_a_new_operation() -> None:
    runtime = build_runtime()
    event = TranscriptEvent(text="stop", confidence=1.0, language="en", is_final=True)

    await runtime.orchestrator.process_event(event)
    outputs = await _drain_available(runtime.output_bus)

    assert [type(output) for output in outputs] == [Intent, ActionPlan, ActionResult]
    assert outputs[2].message == "No operation is currently running."
    assert runtime.operations.has_active_operation is False
    assert runtime.audit.list()[-1].category == "system.control"


@pytest.mark.asyncio
async def test_orchestrator_run_until_closed_drains_input_bus() -> None:
    opened: list[str] = []
    input_bus = EventBus(max_size=5)
    output_bus = EventBus(max_size=5)
    runtime = build_runtime(
        browser_opener=lambda url: not opened.append(url),
        input_bus=input_bus,
        output_bus=output_bus,
    )
    await input_bus.publish(
        TranscriptEvent(text="open youtube", confidence=0.9, language="en", is_final=True)
    )
    input_bus.close()

    await runtime.orchestrator.run_until_closed()

    outputs = await _drain_available(output_bus)
    assert opened == ["https://youtube.com/"]
    assert isinstance(outputs[-1], ActionResult)


@pytest.mark.asyncio
async def test_orchestrator_handles_closed_output_bus_without_crashing() -> None:
    output_bus = EventBus(max_size=1)
    output_bus.close()
    runtime = build_runtime(output_bus=output_bus)
    event = TranscriptEvent(text="what time is it", confidence=1.0, language="en", is_final=True)

    await runtime.orchestrator.process_event(event)

    assert runtime.state_machine.state is AppState.IDLE


@pytest.mark.asyncio
async def test_orchestrator_publishes_error_event_for_domain_error() -> None:
    state = StateMachine(AppState.STOPPED)
    runtime = build_runtime(state_machine=state)
    event = TranscriptEvent(text="what time is it", confidence=1.0, language="en", is_final=True)

    await runtime.orchestrator.process_event(event)
    outputs = await _drain_available(runtime.output_bus)

    assert any(isinstance(output, ErrorEvent) for output in outputs)
