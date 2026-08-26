"""Bounded asynchronous event bus."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress

from visionai.core.errors import EventBusClosed
from visionai.core.events import EventBase


class EventBus:
    """A bounded queue with explicit close semantics and backpressure.

    Closing never discards events already queued: next_event() drains them
    first and only raises EventBusClosed once the queue is empty. The
    close signal itself travels over a separate asyncio.Event rather than
    a sentinel value placed on the queue, so it can never be lost even if
    the queue is completely full at the moment close() is called.
    """

    def __init__(self, max_size: int) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be greater than zero")
        self._queue: asyncio.Queue[EventBase] = asyncio.Queue(maxsize=max_size)
        self._closed_event = asyncio.Event()

    @property
    def closed(self) -> bool:
        return self._closed_event.is_set()

    @property
    def size(self) -> int:
        return self._queue.qsize()

    async def publish(self, event: EventBase) -> None:
        if self.closed:
            raise EventBusClosed("event bus is closed")
        await self._queue.put(event)

    async def next_event(self) -> EventBase:
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            pass

        get_task = asyncio.ensure_future(self._queue.get())
        closed_task = asyncio.ensure_future(self._closed_event.wait())
        try:
            done, _ = await asyncio.wait(
                {get_task, closed_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if get_task in done:
                return get_task.result()
            raise EventBusClosed("event bus is closed")
        finally:
            for task in (get_task, closed_task):
                if not task.done():
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task

    async def subscribe(self) -> AsyncIterator[EventBase]:
        while True:
            try:
                yield await self.next_event()
            except EventBusClosed:
                return

    def close(self) -> None:
        self._closed_event.set()
