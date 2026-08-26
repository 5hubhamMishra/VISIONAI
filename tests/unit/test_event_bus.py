import asyncio

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


@pytest.mark.asyncio
async def test_close_signal_is_not_lost_when_the_queue_is_full() -> None:
    """Regression: closing a full bus must not deadlock next_event().

    close() used to place a sentinel value onto the same bounded queue,
    which is silently dropped if the queue has no free capacity at that
    moment -- leaving subscribers blocked forever with no way to observe
    that the bus closed.
    """
    bus = EventBus(max_size=1)
    await bus.publish(TranscriptEvent(text="one", confidence=1.0, language="en", is_final=True))

    bus.close()  # queue is completely full here

    drained = await asyncio.wait_for(bus.next_event(), timeout=1)
    assert drained.text == "one"

    with pytest.raises(EventBusClosed):
        await asyncio.wait_for(bus.next_event(), timeout=1)


@pytest.mark.asyncio
async def test_subscribe_drains_queued_events_before_stopping_on_close() -> None:
    bus = EventBus(max_size=2)
    await bus.publish(TranscriptEvent(text="one", confidence=1.0, language="en", is_final=True))
    await bus.publish(TranscriptEvent(text="two", confidence=1.0, language="en", is_final=True))
    bus.close()

    received = [event.text async for event in bus.subscribe()]

    assert received == ["one", "two"]
