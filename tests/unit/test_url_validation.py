import pytest

from visionai.core.errors import UrlValidationError
from visionai.policy import UrlPolicy


def test_url_policy_normalizes_allowlisted_https_url() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"example.com"}))

    assert policy.normalize_url("HTTPS://example.com/path here?a=one two") == (
        "https://example.com/path+here?a=one+two"
    )


def test_url_policy_drops_fragments_and_trailing_dot_host() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"example.com"}))

    assert policy.normalize_url("https://example.com./a#token") == "https://example.com/a"


def test_url_policy_rejects_unsafe_scheme() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"example.com"}))

    with pytest.raises(UrlValidationError):
        policy.normalize_url("file://example.com/secrets")


def test_url_policy_rejects_unallowlisted_host() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"example.com"}))

    with pytest.raises(UrlValidationError):
        policy.normalize_url("https://evil.example")


def test_url_policy_rejects_local_and_private_hosts_by_default() -> None:
    policy = UrlPolicy()

    with pytest.raises(UrlValidationError):
        policy.normalize_url("https://localhost/status")

    with pytest.raises(UrlValidationError):
        policy.normalize_url("https://127.0.0.1/status")

    with pytest.raises(UrlValidationError):
        policy.normalize_url("https://192.168.1.10/status")


def test_url_policy_rejects_embedded_credentials() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"example.com"}))

    with pytest.raises(UrlValidationError):
        policy.normalize_url("https://user:pass@example.com/")


def test_url_policy_rejects_unapproved_ports() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"example.com"}))

    with pytest.raises(UrlValidationError):
        policy.normalize_url("https://example.com:444/")


def test_url_policy_rejects_host_confusion_and_redirect_host_changes() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"example.com"}))

    with pytest.raises(UrlValidationError):
        policy.normalize_url("https://example.com.evil.test/")

    with pytest.raises(UrlValidationError):
        policy.validate_redirect("https://example.com/start", "https://evil.test/end")


def test_url_policy_normalizes_idn_hosts_before_allowlist_check() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"xn--bcher-kva.example"}))

    assert policy.normalize_url("https://bücher.example/") == (
        "https://xn--bcher-kva.example/"
    )


def test_search_url_encodes_query_and_rejects_empty_query() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"www.google.com"}))

    assert policy.build_search_url("hello world") == "https://www.google.com/search?q=hello+world"

    with pytest.raises(UrlValidationError):
        policy.build_search_url("  ")
