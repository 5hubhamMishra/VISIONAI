"""Tests for the secret storage boundary: precedence and the in-memory test double.

`KeyringSecretStore` itself is only exercised by one real-backend smoke test
(mirroring `list_input_devices()`/`classify_hand_frame()`'s existing
real-backend smoke-test precedent) -- everything else uses
`InMemorySecretStore`, with no real OS keychain touched.
"""

from __future__ import annotations

from visionai.config.secrets import (
    InMemorySecretStore,
    KeyringSecretStore,
    resolve_anthropic_api_key,
)
from visionai.config.settings import Settings


def test_in_memory_secret_store_round_trips() -> None:
    store = InMemorySecretStore()

    assert store.get("a") is None
    store.set("a", "value")
    assert store.get("a") == "value"
    store.delete("a")
    assert store.get("a") is None


def test_in_memory_secret_store_delete_is_idempotent() -> None:
    store = InMemorySecretStore()

    store.delete("never-set")  # must not raise


def test_resolve_prefers_the_env_var_when_set() -> None:
    settings = Settings(anthropic_api_key="from-env")
    store = InMemorySecretStore()
    store.set("anthropic_api_key", "from-keychain")

    assert resolve_anthropic_api_key(settings, store) == "from-env"


def test_resolve_falls_back_to_the_keychain_when_env_var_unset() -> None:
    settings = Settings()
    store = InMemorySecretStore()
    store.set("anthropic_api_key", "from-keychain")

    assert resolve_anthropic_api_key(settings, store) == "from-keychain"


def test_resolve_returns_none_when_neither_source_has_it() -> None:
    settings = Settings()
    store = InMemorySecretStore()

    assert resolve_anthropic_api_key(settings, store) is None


def test_keyring_secret_store_runs_against_the_real_backend() -> None:
    """Real-backend smoke test: proves the actual OS keychain backend loads
    and responds, without asserting a specific stored value (mirrors
    `list_input_devices()`'s real-PortAudio smoke test)."""

    store = KeyringSecretStore()

    result = store.get("visionai-test-secrets-py-key-that-should-not-exist")

    assert result is None or isinstance(result, str)
