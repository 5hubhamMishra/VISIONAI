"""Safe browser capabilities.

Migrated from the old prototype's web/search behavior as reference
material only. These handlers never accept an arbitrary destination:
known sites are mapped from an allowlist, and searches are constructed by
`UrlPolicy` so query text is encoded before the browser sees it.
"""

from __future__ import annotations

import webbrowser
from collections.abc import Callable, Mapping

from visionai.capabilities.dispatcher import CapabilityHandler
from visionai.capabilities.manifest import (
    CapabilityManifest,
    IdempotencyMode,
    ParameterSpec,
    ParameterType,
)
from visionai.core.errors import UrlValidationError
from visionai.core.events import ActionRequest, ActionResult, RiskLevel
from visionai.policy.url_validation import UrlPolicy

ALLOWED_SITES: Mapping[str, str] = {
    "facebook": "https://facebook.com",
    "github": "https://github.com",
    "instagram": "https://instagram.com",
    "netflix": "https://netflix.com",
    "reddit": "https://reddit.com",
    "twitter": "https://twitter.com",
    "youtube": "https://youtube.com",
}

ALLOWED_BROWSER_HOSTS = frozenset(
    {
        "facebook.com",
        "github.com",
        "instagram.com",
        "netflix.com",
        "reddit.com",
        "twitter.com",
        "youtube.com",
        "www.google.com",
    }
)

BrowserOpener = Callable[[str], bool]


def default_browser_opener(url: str) -> bool:
    """Open `url` in the default browser."""

    return webbrowser.open(url)


def default_browser_policy() -> UrlPolicy:
    """Return the browser capability URL policy."""

    return UrlPolicy(allowed_hosts=ALLOWED_BROWSER_HOSTS)


def browser_open_manifest() -> CapabilityManifest:
    """Return the manifest for opening one allowlisted website."""

    return CapabilityManifest(
        id="browser.open",
        description="Open one allowlisted website in the default browser.",
        parameters={
            "site": ParameterSpec(
                type=ParameterType.STRING,
                required=True,
                description=f"One of: {', '.join(sorted(ALLOWED_SITES))}.",
            )
        },
        risk_level=RiskLevel.REVERSIBLE,
        rate_limit_per_minute=20,
        timeout_seconds=5,
        idempotency=IdempotencyMode.NON_IDEMPOTENT,
        audit_category="browser.open",
        handler_id="browser.open",
    )


def browser_search_manifest() -> CapabilityManifest:
    """Return the manifest for an allowlisted web search."""

    return CapabilityManifest(
        id="browser.search",
        description="Open an encoded web search in the default browser.",
        parameters={
            "query": ParameterSpec(
                type=ParameterType.STRING,
                required=True,
                description="Search text to encode into the allowlisted search URL.",
            )
        },
        risk_level=RiskLevel.REVERSIBLE,
        rate_limit_per_minute=20,
        timeout_seconds=5,
        idempotency=IdempotencyMode.NON_IDEMPOTENT,
        audit_category="browser.search",
        handler_id="browser.search",
    )


def browser_manifests() -> tuple[CapabilityManifest, ...]:
    """Return all built-in browser capability manifests."""

    return (browser_open_manifest(), browser_search_manifest())


def make_browser_open_handler(
    opener: BrowserOpener = default_browser_opener,
    policy: UrlPolicy | None = None,
) -> CapabilityHandler:
    """Create a handler that opens one allowlisted site."""

    policy = policy or default_browser_policy()

    def handle(request: ActionRequest) -> ActionResult:
        requested = str(request.arguments.get("site", "")).strip().lower()
        raw_url = ALLOWED_SITES.get(requested)
        if raw_url is None:
            return ActionResult(
                request_id=request.id,
                success=False,
                message=f"'{requested}' is not an allowlisted website.",
            )
        try:
            url = policy.normalize_url(raw_url)
        except UrlValidationError as exc:
            return ActionResult(
                request_id=request.id,
                success=False,
                message=f"Blocked website: {exc}",
            )
        if not opener(url):
            return ActionResult(
                request_id=request.id,
                success=False,
                message=f"Could not open {requested}.",
            )
        return ActionResult(request_id=request.id, success=True, message=f"Opening {requested}.")

    return handle


def make_browser_search_handler(
    opener: BrowserOpener = default_browser_opener,
    policy: UrlPolicy | None = None,
) -> CapabilityHandler:
    """Create a handler that opens an encoded allowlisted search URL."""

    policy = policy or default_browser_policy()

    def handle(request: ActionRequest) -> ActionResult:
        query = str(request.arguments.get("query", ""))
        try:
            url = policy.build_search_url(query)
        except UrlValidationError as exc:
            return ActionResult(
                request_id=request.id,
                success=False,
                message=f"Blocked search: {exc}",
            )
        if not opener(url):
            return ActionResult(
                request_id=request.id,
                success=False,
                message="Could not open search.",
            )
        return ActionResult(request_id=request.id, success=True, message=f"Searching for: {query}.")

    return handle


def browser_handlers(
    opener: BrowserOpener = default_browser_opener,
    policy: UrlPolicy | None = None,
) -> dict[str, CapabilityHandler]:
    """Return all built-in browser handlers."""

    policy = policy or default_browser_policy()

    return {
        "browser.open": make_browser_open_handler(opener, policy),
        "browser.search": make_browser_search_handler(opener, policy),
    }
