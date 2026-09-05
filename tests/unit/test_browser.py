import visionai.capabilities.browser as browser_module
from visionai.capabilities import CapabilityRegistry
from visionai.capabilities.browser import (
    ALLOWED_SITES,
    browser_manifests,
    browser_open_manifest,
    browser_search_manifest,
    default_browser_opener,
    make_browser_open_handler,
    make_browser_search_handler,
)
from visionai.core.cancellation import CancellationToken
from visionai.core.events import ActionRequest, RiskLevel
from visionai.policy import PolicyContext, UrlPolicy
from visionai.runtime import build_runtime

_TOKEN = CancellationToken()


def _browser_open_request(site: str | None = None, **extra: str) -> ActionRequest:
    arguments = dict(extra)
    if site is not None:
        arguments["site"] = site
    return ActionRequest(
        capability_id="browser.open",
        risk_level=RiskLevel.REVERSIBLE,
        arguments=arguments,
    )


def _browser_search_request(query: str | None = None, **extra: str) -> ActionRequest:
    arguments = dict(extra)
    if query is not None:
        arguments["query"] = query
    return ActionRequest(
        capability_id="browser.search",
        risk_level=RiskLevel.REVERSIBLE,
        arguments=arguments,
    )


def test_browser_manifests_register_as_reversible() -> None:
    registry = CapabilityRegistry(browser_manifests())

    assert registry.get("browser.open").risk_level == RiskLevel.REVERSIBLE
    assert registry.get("browser.search").risk_level == RiskLevel.REVERSIBLE


def test_browser_open_handler_opens_normalized_allowlisted_site() -> None:
    opened: list[str] = []
    handler = make_browser_open_handler(opener=lambda url: not opened.append(url))

    result = handler(_browser_open_request("  GitHub  "), _TOKEN)

    assert result.success is True
    assert opened == ["https://github.com/"]


def test_browser_open_handler_rejects_unknown_site_without_opening() -> None:
    opened: list[str] = []
    handler = make_browser_open_handler(opener=lambda url: not opened.append(url))

    result = handler(_browser_open_request("evil"), _TOKEN)

    assert result.success is False
    assert "not an allowlisted website" in result.message
    assert opened == []


def test_browser_open_handler_blocks_policy_failure_before_opening() -> None:
    opened: list[str] = []
    handler = make_browser_open_handler(
        opener=lambda url: not opened.append(url),
        policy=UrlPolicy(allowed_hosts=frozenset({"example.com"})),
    )

    result = handler(_browser_open_request("github"), _TOKEN)

    assert result.success is False
    assert "Blocked website" in result.message
    assert opened == []


def test_browser_search_handler_builds_encoded_allowlisted_search_url() -> None:
    opened: list[str] = []
    handler = make_browser_search_handler(opener=lambda url: not opened.append(url))

    result = handler(_browser_search_request("jarvis & vision ai"), _TOKEN)

    assert result.success is True
    assert opened == ["https://www.google.com/search?q=jarvis+%26+vision+ai"]


def test_browser_search_handler_rejects_empty_query_without_opening() -> None:
    opened: list[str] = []
    handler = make_browser_search_handler(opener=lambda url: not opened.append(url))

    result = handler(_browser_search_request("  "), _TOKEN)

    assert result.success is False
    assert "search query is empty" in result.message
    assert opened == []


def test_default_browser_opener_delegates_to_webbrowser_open(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(browser_module.webbrowser, "open", lambda url: calls.append(url) or True)

    assert default_browser_opener("https://example.com") is True
    assert calls == ["https://example.com"]


def test_browser_open_handler_reports_failure_when_opener_returns_false() -> None:
    handler = make_browser_open_handler(opener=lambda url: False)

    result = handler(_browser_open_request("github"), _TOKEN)

    assert result.success is False
    assert result.message == "Could not open github."


def test_browser_search_handler_reports_failure_when_opener_returns_false() -> None:
    handler = make_browser_search_handler(opener=lambda url: False)

    result = handler(_browser_search_request("weather"), _TOKEN)

    assert result.success is False
    assert result.message == "Could not open search."


def test_browser_search_handler_rejects_control_characters_without_opening() -> None:
    opened: list[str] = []
    handler = make_browser_search_handler(opener=lambda url: not opened.append(url))

    result = handler(_browser_search_request("hello\nworld"), _TOKEN)

    assert result.success is False
    assert "control characters" in result.message
    assert opened == []


def test_runtime_dispatches_browser_open_and_audits_it() -> None:
    opened: list[str] = []
    runtime = build_runtime(browser_opener=lambda url: not opened.append(url))

    result = runtime.dispatcher.dispatch(_browser_open_request("youtube"), PolicyContext())

    assert result.success is True
    assert opened == [ALLOWED_SITES["youtube"] + "/"]
    audited = runtime.audit.list()[-1]
    assert audited.category == "browser.open"
    assert audited.risk_level == RiskLevel.REVERSIBLE


def test_runtime_dispatches_browser_search() -> None:
    opened: list[str] = []
    runtime = build_runtime(browser_opener=lambda url: not opened.append(url))

    result = runtime.dispatcher.dispatch(_browser_search_request("weather today"), PolicyContext())

    assert result.success is True
    assert opened == ["https://www.google.com/search?q=weather+today"]


def test_policy_rejects_missing_and_unknown_browser_arguments() -> None:
    runtime = build_runtime(browser_opener=lambda url: True)

    missing_open = runtime.dispatcher.dispatch(_browser_open_request(), PolicyContext())
    unknown_open = runtime.dispatcher.dispatch(
        _browser_open_request("github", x="1"), PolicyContext()
    )
    missing_search = runtime.dispatcher.dispatch(_browser_search_request(), PolicyContext())
    unknown_search = runtime.dispatcher.dispatch(
        _browser_search_request("hello", site="github"), PolicyContext()
    )

    assert missing_open.success is False
    assert missing_open.message == "missing required argument: site"
    assert unknown_open.success is False
    assert unknown_open.message == "unknown argument: x"
    assert missing_search.success is False
    assert missing_search.message == "missing required argument: query"
    assert unknown_search.success is False
    assert unknown_search.message == "unknown argument: site"


def test_browser_manifest_helpers_have_expected_parameters() -> None:
    assert set(browser_open_manifest().parameters) == {"site"}
    assert set(browser_search_manifest().parameters) == {"query"}
