"""LLM provider boundary: conversation only, no execution authority.

Mirrors `visionai.platform.lock_state`'s Protocol/static-fallback/real-
implementation shape. `LLMProvider` returns free text handed straight back
to the caller -- it is never parsed as a command, never reaches the policy
engine or dispatcher, and cannot invoke a capability. That authority
boundary is what makes a provider safe to swap (cloud, local, or none)
without touching anything else in the runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from visionai.core.events import SafeText

_FALLBACK_MESSAGE = (
    "No LLM provider is configured. Set VISIONAI_LLM_PROVIDER=anthropic and "
    "VISIONAI_ANTHROPIC_API_KEY to enable conversational answers."
)


class LLMQuery(BaseModel):
    """One validated, bounded question -- never raw unchecked text."""

    text: SafeText


class LLMReply(BaseModel):
    """One validated, bounded answer."""

    text: SafeText


class LLMProvider(Protocol):
    """Produces one reply per query. Synchronous, like other adapter boundaries."""

    def respond(self, query: LLMQuery) -> LLMReply:
        """Return a conversational reply. Must never execute anything."""


@dataclass(frozen=True, slots=True)
class DeterministicFallbackProvider:
    """Always-available provider: no network, no key, no external dependency.

    The default when no provider is configured, so the app never makes a
    network call unless a user has explicitly opted in.
    """

    def respond(self, query: LLMQuery) -> LLMReply:
        return LLMReply(text=_FALLBACK_MESSAGE)
