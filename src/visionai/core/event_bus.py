"""Bounded asynchronous event bus."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress

from visionai.core.errors import EventBusClosed
from visionai.core.events import EventBase


class EventBus:
    """A bounded queue with explicit close semantics and backpressure."""

    def __init__(self, max_size: int) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be greater than zero")
        self._queue: asyncio.Queue[EventBase | None] = asyncio.Queue(maxsize=max_size)
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def size(self) -> int:
        return self._queue.qsize()

    async def publish(self, event: EventBase) -> None:
        if self._closed:
            raise EventBusClosed("event bus is closed")
        await self._queue.put(event)

    async def next_event(self) -> EventBase:
        event = await self._queue.get()
        if event is None:
            self._queue.task_done()
            raise EventBusClosed("event bus is closed")
        self._queue.task_done()
        return event

    async def subscribe(self) -> AsyncIterator[EventBase]:
        while True:
            try:
                yield await self.next_event()
            except EventBusClosed:
                return

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with suppress(asyncio.QueueFull):
            self._queue.put_nowait(None)
