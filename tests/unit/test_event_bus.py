import pytest

from visionai.core.errors import EventBusClosed
from visionai.core.event_bus import EventBus
from visionai.core.events import TranscriptEvent


@pytest.mark.asyncio
async def test_event_bus_publishes_events_in_order() -> None:
    bus = EventBus(max_size=2)
    first = TranscriptEvent(text="one", confidence=1.0, language="en", is_final=True)
    second = TranscriptEvent(text="two", confidence=1.0, language="en", is_final=True)

    await bus.publish(first)
    await bus.publish(second)

    assert await bus.next_event() == first
    assert await bus.next_event() == second


@pytest.mark.asyncio
async def test_event_bus_rejects_publish_after_close() -> None:
    bus = EventBus(max_size=1)
    bus.close()

    with pytest.raises(EventBusClosed):
        await bus.publish(
            TranscriptEvent(text="late", confidence=1.0, language="en", is_final=True)
        )
