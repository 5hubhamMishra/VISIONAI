"""LLM provider boundary: conversation only, no execution authority.

`anthropic_provider`/`local_provider` are deliberately not re-exported here,
mirroring `visionai.platform.__init__` not re-exporting `webcam`/
`microphone` -- importing `visionai.intelligence` must never require the
`intelligence` extra (the `anthropic` package) or the `local_llm` extra
(the `gpt4all` package) to be installed.
"""

from visionai.intelligence.memory import ConversationMemory, ConversationTurn
from visionai.intelligence.planner import suggest_command
from visionai.intelligence.provider import (
    DeterministicFallbackProvider,
    LLMProvider,
    LLMQuery,
    LLMReply,
)

__all__ = [
    "ConversationMemory",
    "ConversationTurn",
    "DeterministicFallbackProvider",
    "LLMProvider",
    "LLMQuery",
    "LLMReply",
    "suggest_command",
]
