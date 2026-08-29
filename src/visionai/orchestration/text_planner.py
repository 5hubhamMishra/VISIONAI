"""Deterministic text-command planning.

This is not an LLM planner and not a voice recognizer. It accepts already
captured text, matches a small set of reviewed phrases, and emits typed
`ActionRequest`s only for capabilities already registered in the runtime.
Everything else becomes non-executable conversation data.
"""

from __future__ import annotations

import re

from visionai.capabilities.applications import ALLOWED_APPLICATIONS
from visionai.capabilities.browser import ALLOWED_SITES
from visionai.capabilities.media import ALLOWED_MEDIA_ACTIONS
from visionai.capabilities.registry import CapabilityRegistry
from visionai.core.events import ActionPlan, ActionRequest, Intent

_SPACE = re.compile(r"\s+")
_SAFE_SLOT = re.compile(r"^[a-z0-9 _.-]+$")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_APP_PHRASE = re.compile(r"^(?:open|launch|start)\s+(.+)$")
_SITE_PHRASE = re.compile(r"^(?:open|go to|visit)\s+(.+)$")
_SEARCH_PHRASE = re.compile(r"^(?:search(?: for)?|google|find|look up)\s+(.+)$")
_APP_ALIASES = {"notebook": "notepad"}

_DIRECT_CAPABILITIES = {
    "help": "system.help",
    "what can you do": "system.help",
    "capabilities": "system.capabilities",
    "list capabilities": "system.capabilities",
    "clear history": "system.clear_history",
    "clear audit history": "system.clear_history",
    "delete history": "system.clear_history",
    "delete audit history": "system.clear_history",
    "stop": "system.stop",
    "cancel": "system.stop",
    "what time is it": "system.time",
    "time": "system.time",
    "what is the date": "system.date",
    "date": "system.date",
    "today": "system.date",
    "battery": "system.battery",
    "battery status": "system.battery",
    "system health": "system.health",
    "health": "system.health",
}

# Overrides the generic "Run <capability>." summary for capabilities whose
# summary is actually shown to the user in a confirmation/permission prompt
# (Section 9: "must display exact normalized action, target and effect").
# Read-only direct phrases never reach a prompt, so a generic summary for
# them is harmless; system.clear_history does, so it needs a real one.
_DIRECT_SUMMARIES = {
    "system.clear_history": "Clear the local audit history.",
}

_MEDIA_PHRASES = {
    "mute": "mute",
    "volume mute": "mute",
    "volume up": "volume_up",
    "increase volume": "volume_up",
    "volume down": "volume_down",
    "decrease volume": "volume_down",
    "play": "play_pause",
    "pause": "play_pause",
    "resume": "play_pause",
    "play pause": "play_pause",
    "next": "next",
    "next track": "next",
    "previous": "previous",
    "previous track": "previous",
}


class TextCommandPlanner:
    """Plan a typed user command into at most one registered action."""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    def plan(self, text: str) -> tuple[Intent, ActionPlan]:
        """Return a typed intent and action plan for `text`."""

        normalized = _normalize_text(text)
        if not normalized:
            return self._empty_plan(text, "Empty command.")

        direct = _DIRECT_CAPABILITIES.get(normalized)
        if direct:
            return self._capability_plan(
                source_text=text,
                intent_name=direct,
                capability_id=direct,
                arguments={},
                summary=_DIRECT_SUMMARIES.get(direct, f"Run {direct}."),
            )

        media_action = _MEDIA_PHRASES.get(normalized)
        if media_action and media_action in ALLOWED_MEDIA_ACTIONS:
            return self._capability_plan(
                source_text=text,
                intent_name="media.control",
                capability_id="media.control",
                arguments={"action": media_action},
                summary=f"Send media action {media_action}.",
            )

        for pattern, planner in (
            (_APP_PHRASE, self._plan_app_open),
            (_SITE_PHRASE, self._plan_browser_open),
            (_SEARCH_PHRASE, self._plan_browser_search),
        ):
            match = pattern.match(normalized)
            if match:
                planned = planner(text, match.group(1).strip())
                if planned is not None:
                    return planned

        return self._empty_plan(text, "No executable action selected.")

    def _plan_app_open(self, source_text: str, app: str) -> tuple[Intent, ActionPlan] | None:
        app = _APP_ALIASES.get(app, app)
        if not _is_safe_name(app) or app not in ALLOWED_APPLICATIONS:
            return None
        return self._capability_plan(
            source_text=source_text,
            intent_name="app.open",
            capability_id="app.open",
            arguments={"app": app},
            summary=f"Open {app}.",
        )

    def _plan_browser_open(self, source_text: str, site: str) -> tuple[Intent, ActionPlan] | None:
        if not _is_safe_name(site) or site not in ALLOWED_SITES:
            return None
        return self._capability_plan(
            source_text=source_text,
            intent_name="browser.open",
            capability_id="browser.open",
            arguments={"site": site},
            summary=f"Open {site}.",
        )

    def _plan_browser_search(
        self, source_text: str, query: str
    ) -> tuple[Intent, ActionPlan] | None:
        if any(ord(char) < 32 or ord(char) == 127 for char in query) or not query.strip():
            return None
        return self._capability_plan(
            source_text=source_text,
            intent_name="browser.search",
            capability_id="browser.search",
            arguments={"query": query},
            summary=f"Search for {query}.",
        )

    def _capability_plan(
        self,
        *,
        source_text: str,
        intent_name: str,
        capability_id: str,
        arguments: dict[str, str],
        summary: str,
    ) -> tuple[Intent, ActionPlan]:
        manifest = self._registry.get(capability_id)
        intent = Intent(
            name=intent_name,
            confidence=0.9,
            slots=arguments,
            source_text=source_text,
        )
        request = ActionRequest(
            capability_id=capability_id,
            arguments=arguments,
            risk_level=manifest.risk_level,
        )
        return intent, ActionPlan(steps=(request,), summary=summary)

    @staticmethod
    def _empty_plan(source_text: str, summary: str) -> tuple[Intent, ActionPlan]:
        # The rejection decision (no match, or a slot that failed validation)
        # was already made against the raw text; this only sanitizes what
        # goes into the informational Intent below, which carries no
        # executable authority (steps stays empty regardless).
        safe_text = _CONTROL_CHARS.sub("", source_text)
        intent = Intent(
            name="conversation.reply",
            confidence=0.3,
            slots={"text": safe_text},
            source_text=safe_text,
        )
        return intent, ActionPlan(steps=(), summary=summary)


def _normalize_text(text: str) -> str:
    return _SPACE.sub(" ", text.strip().lower())


def _is_safe_name(value: str) -> bool:
    return bool(_SAFE_SLOT.fullmatch(value))
