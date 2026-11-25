"""Event bus interface and in-memory adapter (plan §2.2, §3, Appendix B; ADR-0008).

NATS JetStream replaces the in-memory adapter when it runs (ADR-0002, OD-10).
Only the subjects defined in ``edp_contracts.events`` can be published.
"""

import itertools
from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel

from edp_contracts.events import ALL_SUBJECTS


class UnknownSubjectError(ValueError):
    pass


class Event(BaseModel):
    seq: int
    subject: str
    payload: dict[str, Any]


Handler = Callable[[Event], None]


class EventBus(Protocol):
    def publish(self, subject: str, payload: dict[str, Any]) -> Event: ...
    def subscribe(self, prefix: str, handler: Handler) -> None: ...


class InMemoryEventBus:
    """Synchronous bus that keeps every event, for local runs and tests."""

    def __init__(self) -> None:
        self.history: list[Event] = []
        self._handlers: list[tuple[str, Handler]] = []
        self._seq = itertools.count(1)

    def publish(self, subject: str, payload: dict[str, Any]) -> Event:
        if subject not in ALL_SUBJECTS:
            raise UnknownSubjectError(subject)
        event = Event(seq=next(self._seq), subject=subject, payload=payload)
        self.history.append(event)
        for prefix, handler in self._handlers:
            if subject.startswith(prefix):
                handler(event)
        return event

    def subscribe(self, prefix: str, handler: Handler) -> None:
        self._handlers.append((prefix, handler))

    def subjects(self) -> list[str]:
        return [e.subject for e in self.history]
