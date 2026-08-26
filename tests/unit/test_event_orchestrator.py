import pytest

from visionai.core.event_bus import EventBus
from visionai.core.events import ActionPlan, ActionResult, ErrorEvent, Intent, TranscriptEvent
from visionai.core.state import AppState, StateMachine
from visionai.runtime import build_runtime


async def _drain_available(bus: EventBus):
    events = []
    while bus.size:
        events.append(await bus.next_event())
    return events


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
