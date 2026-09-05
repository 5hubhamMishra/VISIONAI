"""Tests for the secret storage boundary: precedence and the in-memory test double.

`KeyringSecretStore` itself is only exercised by one real-backend smoke test
(mirroring `list_input_devices()`/`classify_hand_frame()`'s existing
real-backend smoke-test precedent) -- everything else uses
`InMemorySecretStore`, with no real OS keychain touched.
"""

from __future__ import annotations

import keyring
import keyring.errors
import pytest

from visionai.config.secrets import (
    InMemorySecretStore,
    KeyringSecretStore,
    resolve_anthropic_api_key,
)
from visionai.config.settings import Settings
from visionai.core.errors import StorageError


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


def test_keyring_secret_store_set_calls_the_backend_with_the_service_and_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        keyring,
        "set_password",
        lambda service, key, value: calls.append((service, key, value)),
    )
    store = KeyringSecretStore()

    store.set("anthropic_api_key", "secret-value")

    assert calls == [("visionai", "anthropic_api_key", "secret-value")]


def test_keyring_secret_store_set_wraps_a_backend_failure_as_storage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(service: str, key: str, value: str) -> None:
        raise RuntimeError("backend unavailable")

    monkeypatch.setattr(keyring, "set_password", _raise)
    store = KeyringSecretStore()

    with pytest.raises(StorageError):
        store.set("anthropic_api_key", "secret-value")


def test_keyring_secret_store_delete_calls_the_backend_with_the_service_and_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        keyring, "delete_password", lambda service, key: calls.append((service, key))
    )
    store = KeyringSecretStore()

    store.delete("anthropic_api_key")

    assert calls == [("visionai", "anthropic_api_key")]


def test_keyring_secret_store_delete_is_idempotent_when_nothing_was_stored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(service: str, key: str) -> None:
        raise keyring.errors.PasswordDeleteError("not found")

    monkeypatch.setattr(keyring, "delete_password", _raise)
    store = KeyringSecretStore()

    store.delete("never-stored")  # must not raise


def test_keyring_secret_store_delete_wraps_other_backend_failures_as_storage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(service: str, key: str) -> None:
        raise RuntimeError("backend unavailable")

    monkeypatch.setattr(keyring, "delete_password", _raise)
    store = KeyringSecretStore()

    with pytest.raises(StorageError):
        store.delete("anthropic_api_key")
