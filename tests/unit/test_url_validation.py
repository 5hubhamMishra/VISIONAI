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


def test_url_policy_rejects_control_characters_in_the_raw_url() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"example.com"}))

    with pytest.raises(UrlValidationError, match="control characters"):
        policy.normalize_url("https://example.com/\x00path")


def test_url_policy_rejects_unsafe_scheme() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"example.com"}))

    with pytest.raises(UrlValidationError):
        policy.normalize_url("file://example.com/secrets")


def test_url_policy_rejects_unallowlisted_host() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"example.com"}))

    with pytest.raises(UrlValidationError):
        policy.normalize_url("https://evil.example")


def test_url_policy_denies_public_host_when_allowlist_is_empty() -> None:
    """An unconfigured allowlist must deny, not silently allow, every public host."""
    policy = UrlPolicy()

    with pytest.raises(UrlValidationError):
        policy.normalize_url("https://not-actually-allowlisted.example/")


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


def test_url_policy_rejects_host_confusion() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"example.com"}))

    with pytest.raises(UrlValidationError):
        policy.normalize_url("https://example.com.evil.test/")


def test_validate_redirect_rejects_a_redirect_to_a_different_allowlisted_host() -> None:
    """A redirect must land on the original host, even if the target is itself allowlisted."""
    policy = UrlPolicy(allowed_hosts=frozenset({"example.com", "other.example"}))

    with pytest.raises(UrlValidationError, match="redirect host changed"):
        policy.validate_redirect(
            "https://example.com/start", "https://other.example/end"
        )


def test_validate_redirect_accepts_a_same_host_redirect() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"example.com"}))

    assert policy.validate_redirect(
        "https://example.com/start", "https://example.com/end"
    ) == "https://example.com/end"


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


def test_search_url_rejects_an_overly_long_query() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"www.google.com"}))

    with pytest.raises(UrlValidationError, match="too long"):
        policy.build_search_url("a" * 501)


def test_normalize_host_rejects_a_missing_hostname() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"example.com"}))

    with pytest.raises(UrlValidationError, match="host is required"):
        policy.normalize_url("https:///path")


def test_normalize_host_rejects_a_host_that_idna_encoding_cannot_represent() -> None:
    policy = UrlPolicy(allowed_hosts=frozenset({"example.com"}))
    oversized_label = "a" * 64 + ".com"

    with pytest.raises(UrlValidationError, match="host is invalid"):
        policy.normalize_url(f"https://{oversized_label}/")
